from datetime import datetime
import pandas as pd
import numpy as np
import argparse
import os

import sys
sys.path.append('src/utils/')
from data_wrangler import missing_cols, data_cleaning_financial
from scrap_financials import clean_financial_columns, get_common_columns

qtr_excl_cols = ['Exceptional Item_QTR', 'Diluted EPS for continuing operation_QTR', 'Basic EPS for continuing operation_QTR', 'Employee Benefit Expenses_QTR', 'Employee benefit expense_QTR', 'Diluted for discontinued & continuing operation_QTR']

yrly_excl_cols = ['Exceptional Item_YRLY', 'Basic EPS for continuing operation_YRLY', 'Diluted EPS for continuing operation_YRLY', 'Employee Benefit Expenses_YRLY', 'Employee benefit expense_YRLY', 'Diluted for discontinued & continuing operation_YRLY', 'Finance Costs_YRLY', 'Deferred tax_YRLY', 'Basic for discontinued & continuing operation_YRLY', 'Current tax_YRLY', 'Total Income_YRLY', 'Basic & Diluted EPS after Extraordinary items_YRLY', 'Net Sales_YRLY', 'Profit before Interest and Exceptional Items_YRLY', 'Profit from Operations before Other Income, Interest and Exceptional Items_YRLY', 'Equity Capital_YRLY']

tickers = ['AARTIIND.BO', 'EIHOTEL.BO', 'ELGIEQUIP.BO', 'IPCALAB.BO', 'PGHL.BO', 'SONATSOFTW.BO', 'SUPREMEIND.BO', 'TV18BRDCST.BO']

# command to run this script
# python src/scripts/process_data/filter_financial_features.py datasets/rawdata/financial_results/ datasets/processed_data/financial_results/

if __name__ == "__main__":
    start_time = datetime.now()
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT_PATH', help='path from where to read scraped financial resutls')    
    parser.add_argument('OUTPUT_PATH', help='path where to write the financial results filtered dataframe')    
    
    print("script started")
    args = parser.parse_args()    
    result_files = os.listdir(args.INPUT_PATH)
    
    # get common attributes reported across these 5 tickers and 
    qtr_cols = get_common_columns(args.INPUT_PATH, tickers, 'QTR')
    yrly_cols = get_common_columns(args.INPUT_PATH, tickers, 'YRLY')    
    
    for indx, filename in enumerate(result_files):
        # read the downloaded raw financial results
        print(filename)
        fin_df = pd.read_csv(args.INPUT_PATH + filename, low_memory=False)
        
        # filter only predefined colums financial results dataframe
        if 'QTR' in filename:
            # exclude these columns with less data present
            filter_cols = qtr_cols
#             filter_cols = list(set(qtr_cols) - set(qtr_excl_cols))
            print(len(qtr_cols), len(filter_cols))
        else:
            filter_cols = yrly_cols
#             filter_cols = list(set(yrly_cols) - set(yrly_excl_cols))
        fin_df = fin_df[filter_cols].copy()
                            
        # clean and normalize the column names for financial result data
        new_columns = clean_financial_columns(fin_df.columns.tolist())
        fin_df.columns = new_columns
        
        # clean financial features
#         fin_df = data_cleaning_financial(fin_df)
        
        # write the filtered financial features in the privided output path 
        fin_df = fin_df.sort_values('date')
        fin_df.to_csv(args.OUTPUT_PATH + filename, index=False)
        
    end_time = datetime.now()
    running_time = end_time - start_time
    print("Total running time for the job is:", running_time)

    