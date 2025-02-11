import argparse
import os
import sys
import warnings
from urllib.parse import urlparse

import mlflow
import pandas as pd
from mlflow.models.signature import infer_signature
from sklearn.model_selection import train_test_split

sys.path.append('src/utils/')
from data_wrangler import timeseries_to_supervise, fetch_topn_features, create_all_features
from model_utils import evaluate_model, train_model, select_model

import logging
logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)
             
data_paths = {'RAW_DATA': 'datasets/rawdata/market_data/',
                 'FINANCIAL_RESULTS': 'datasets/processed_data/financial_results/',
                 'INDEX_FEATURES': 'datasets/processed_data/index_features/',
                 'COMBINED_FEATURES': 'datasets/processed_data/combined_features/',
                 'AGG_SENTIMENT': 'datasets/processed_data/agg_sentiment_scores/agg_sentiment.csv',
                 'TOPIC_SENTIMENT': 'datasets/processed_data/agg_sentiment_scores/agg_sent_topic.csv',
                 'TICKER_SENTIMENT': 'datasets/processed_data/agg_sentiment_scores/ticker_news_sent.csv',
                 'TICKERS': ['EIHOTEL.BO', 'ELGIEQUIP.BO', 'IPCALAB.BO', 'PGHL.BO',  'TV18BRDCST.BO'],
                 'TOPIC_IDS': [33, 921, 495, 495, 385]
             }

agg_topic_ticker_sent_cols = ['agg_polarity', 'agg_compound', 'topic_polarity', 'topic_compound', 'ticker_polarity', 'ticker_compound']
scoring = 'neg_mean_absolute_percentage_error'
train_size = 0.8  # 80% for training, 20% for testing
window_size = 10  # Number of past records to consider
target_price = 'ln_target'
topn_feature_count = 50
seed= 42

# command to run the script
# python src/scripts/training_evaluation/predict_byLightGBM-woSentiment.py LightGBM LightGBMwoSentiment datasets/processed_data/feature_importance/LightGBM/ datasets/processed_data/model_predictions/LightGBM/woSentiment/ 

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument('MODEL_NAME', help='provide the ml model, for which we want to train/predict the data ')
    parser.add_argument('EXPERIMENT_NAME', help='provide the experiment name, for which to run the training')    
    parser.add_argument('FEATURE_PATH', help='path where to write/read computed shape values for feature importance')    
    parser.add_argument('MODEL_PREDICTIONS', help='path where to write computed shape values for feature importance')
    

    args = parser.parse_args()
    # fetch topn features as per feature importance
    topn_features_df = fetch_topn_features(args.FEATURE_PATH, topn_feature_count)
    topn_features = topn_features_df['feature'].values.tolist()
    topn_features = topn_features + ['yesterday_close', 'ln_target']        
    
    # make predicttions for all tickers 
    for indx, ticker in enumerate(data_paths['TICKERS']):
        topic_id = data_paths['TOPIC_IDS'][indx]
        
        path = data_paths['COMBINED_FEATURES'] + ticker + '.csv.gz'         
        if os.path.isfile(path):
               combined_df = pd.read_csv(path)
        else:            
        # create all the features
            combined_df = create_all_features(data_paths, ticker, topic_id)        
            combined_df.to_csv(path, index=False)

        combined_date_df = combined_df['date']
        combined_df = combined_df.drop(columns='date')        
                
        # do train/test split the data with shuffle = False
        train_data, test_data = train_test_split(combined_df.loc[:, topn_features], train_size=train_size, shuffle=False)
        train_date, test_date = train_test_split(combined_date_df, train_size=train_size, shuffle=False)
        
        # convert timeseries to be used in supervise learning model
        X_train, y_train, indx_train = timeseries_to_supervise(train_data, window_size, target_price)  
                
#       aligned script as per teams conventin of 80/20 train/test split
        # further split test set to have an hold out set to be used for backtesting
#         eval_data, test_data = train_test_split(test_data, train_size=0.5, shuffle=False)
#         eval_date, test_date = train_test_split(test_date, train_size=0.5, shuffle=False)

        # convert timeseries to be used in supervise learning model    
        X_test, y_test, indx_test = timeseries_to_supervise(test_data, window_size, target_price)  
                                    
            
        experiment_name = args.EXPERIMENT_NAME  # Replace with your desired experiment name

        # Create or get the experiment
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            experiment_id = mlflow.create_experiment(experiment_name)
        else:
            experiment_id = experiment.experiment_id

        # Start an MLflow run with the specified experiment name
        with mlflow.start_run(experiment_id=experiment_id):
            # choose the model as per provided arguments
            model = select_model(args.MODEL_NAME, seed)
            
            # train the Random Forest model
            trained_model = train_model(model, X_train, y_train)

            # evaluate the fitted model using mape and rmse metrics
            predictions_df, mape, rmse = evaluate_model(trained_model, window_size, test_data, test_date, X_test, y_test)    
            predictions_df.to_csv(args.MODEL_PREDICTIONS + ticker + '.csv', header=True, index=False)
            print("for ticker {0} mean absolute percentage error: {1}, root_mean_square_error: {2}".format(ticker, round(mape, 4), round(rmse, 4)))
            
            
            mlflow.log_param("ticker", ticker)
            mlflow.log_param("target_price", target_price)
            mlflow.log_param("mape", round(mape, 5))    
            mlflow.log_param("rmse", round(rmse, 5))                
            signature = infer_signature(X_train, predictions_df)

            tracking_url_type_store = urlparse(mlflow.get_tracking_uri()).scheme

            # Model registry does not work with file store
            if tracking_url_type_store != "file":
                # Register the model
                # There are other ways to use the Model Registry, which depends on the use case,
                # please refer to the doc for more information:
                # https://mlflow.org/docs/latest/model-registry.html#api-workflow
                mlflow.sklearn.log_model(
                    trained_model, "model", registered_model_name=args.MODEL_NAME, signature=signature
                )
            else:
                mlflow.sklearn.log_model(trained_model, "model", signature=signature)          