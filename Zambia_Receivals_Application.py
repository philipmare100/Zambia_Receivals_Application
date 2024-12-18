import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# Streamlit app title
st.title("Zambia Warehouse Receiving Supervision - Data Extraction and Combined DataFrame")

# South Africa timezone setup
sa_timezone = pytz.timezone('Africa/Johannesburg')

# File uploader widget
uploaded_file = st.file_uploader("Choose a file", type=['xlsx'])

# If a file is uploaded
if uploaded_file is not None:
    try:
        # Load the data from the "RawData" sheet, skipping the first row (header=1)
        df = pd.read_excel(uploaded_file, sheet_name="RawData", header=1)

        # Ensure "Added Time" is in datetime format and localize for filtering purposes
        if "Added Time" in df.columns:
            df['Added Time'] = pd.to_datetime(df['Added Time'], errors='coerce')
            localized_added_time = df['Added Time'].dt.tz_localize('UTC').dt.tz_convert(sa_timezone)  # Only for filtering
        else:
            st.error("The 'RawData' sheet does not contain an 'Added Time' column.")
            st.stop()

        # Identify columns
        bag_id_column = "BAG ID." if "BAG ID." in df.columns else None
        kico_seal_column = "KICO SEAL NO." if "KICO SEAL NO." in df.columns else None
        mms_seal_column = "MMS BAG SEAL NO" if "MMS BAG SEAL NO" in df.columns else None
        receiving_horse_column = "RECEIVING HORSE REGISTRATION" if "RECEIVING HORSE REGISTRATION" in df.columns else None

        # Check if the required column is present
        if bag_id_column:
            # Extract components from the Bag ID column and create new columns
            def extract_bag_info(bag_id):
                parts = dict(item.split('=') for item in bag_id.split(',') if '=' in item)
                parts.update({item.split(': ')[0]: item.split(': ')[1] for item in bag_id.split(',') if ': ' in item})
                return parts

            # Apply extraction to create new columns from Bag ID details
            bag_info_df = df[bag_id_column].dropna().apply(extract_bag_info).apply(pd.Series)
            combined_df = pd.concat([df, bag_info_df], axis=1)
            combined_df["Bag Scanned & Manual"] = combined_df.apply(
                lambda row: row["Bag"] if len(str(row[bag_id_column])) > 20 else row[bag_id_column],
                axis=1
            )
            combined_df = combined_df.sort_values(by="Added Time", ascending=False)

            # Display the full combined_df with total count
            st.write(f"Total Combined DataFrame Entries: {len(combined_df)}")
            st.write("Combined DataFrame with extracted components (Sorted by Added Time):")
            st.dataframe(combined_df)

            # Exception Table 1: Duplicates in "Bag Scanned & Manual" column
            duplicates_df = combined_df[combined_df.duplicated(subset=["Bag Scanned & Manual"], keep=False)]
            grouped_duplicates = duplicates_df.groupby("Bag Scanned & Manual").apply(
                lambda group: pd.Series({
                    "Added Time": ', '.join(sorted(group["Added Time"].astype(str).unique(), reverse=True)),
                    "Bag Scanned & Manual": group["Bag Scanned & Manual"].iloc[0],
                    "KICO SEAL NO.": ', '.join(group[kico_seal_column].dropna().unique()) if group[
                        kico_seal_column].nunique() > 1 else group[kico_seal_column].iloc[0],
                    "MMS BAG SEAL NO": ', '.join(group[mms_seal_column].dropna().unique()) if mms_seal_column and group[
                        mms_seal_column].nunique() > 1 else group[mms_seal_column].iloc[0] if mms_seal_column else None,
                    "Seal": ', '.join(group["Seal"].dropna().unique()) if group["Seal"].nunique() > 1 else
                    group["Seal"].iloc[0],
                    "Lot": ', '.join(group["Lot"].dropna().unique()) if group["Lot"].nunique() > 1 else
                    group["Lot"].iloc[0],
                    "RECEIVING HORSE REGISTRATION": ', '.join(
                        group[receiving_horse_column].dropna().unique()) if receiving_horse_column and group[
                        receiving_horse_column].nunique() > 1 else group[receiving_horse_column].iloc[0]
                })
            ).reset_index(drop=True).sort_values(by="Added Time", ascending=False)

            st.write(f"Total Duplicates in 'Bag Scanned & Manual': {len(grouped_duplicates)}")
            st.write("Duplicates Exception Table (Consolidated, Based on 'Bag Scanned & Manual'):")
            st.dataframe(grouped_duplicates)

            # Exception Table 2: "BAG ID." entries with length between 16 and 25 characters
            length_exception_df = combined_df[combined_df[bag_id_column].str.len().between(16, 25)]
            length_exception_df = length_exception_df.sort_values(by="Added Time", ascending=False)
            st.write(f"Total 'BAG ID.' Entries with Length Between 16 and 25 Characters: {len(length_exception_df)}")
            st.write("Length Exception Table (Based on 'BAG ID.' Length 16-25):")
            st.dataframe(length_exception_df)

            # Exception Table 3: Entries with dash in "Bag Scanned & Manual"
            dash_exception_df = combined_df[combined_df["Bag Scanned & Manual"].str.contains('-', na=False)]
            dash_exception_df = dash_exception_df.sort_values(by="Added Time", ascending=False)
            st.write(f"Total 'Bag Scanned & Manual' Entries Containing Dash '-': {len(dash_exception_df)}")
            st.write("Dash Exception Table (Based on 'Bag Scanned & Manual' Column):")
            st.dataframe(dash_exception_df)

            # Date-Time Picker for Filtering (localized version of Added Time)
            st.write("Select a date-time range to filter the Combined DataFrame:")
            start_date = st.date_input("Start Date", value=localized_added_time.min().date())
            start_time = st.time_input("Start Time", value=pd.to_datetime("00:00").time())
            end_date = st.date_input("End Date", value=datetime.now(sa_timezone).date())
            end_time = st.time_input("End Time", value=datetime.now(sa_timezone).time())

            # Combine date and time into timezone-aware datetime objects
            start_datetime = sa_timezone.localize(pd.to_datetime(f"{start_date} {start_time}"))
            end_datetime = sa_timezone.localize(pd.to_datetime(f"{end_date} {end_time}"))

            # Filter combined_df based on the selected date-time range using localized_added_time
            filtered_df = combined_df[(localized_added_time >= start_datetime) & (localized_added_time <= end_datetime)]

            # Mapping for column names in the download CSV
            column_mappings = {
                "Bag Scanned & Manual": "name",
                "KICO SEAL NO.": "GRN_KICO_SEAL",
                "MMS BAG SEAL NO": "MMS_SEAL_NO",
                "RECEIVING WAREHOUSE PLATFORM SCALE GROSS WEIGHT (KG)": "GRN_WH_GROSS_WEIGHT",
                "BAG OFFLOADING TIME": "GRN_RECEIVED_DATE",
                "RECORD BAG CONDITION": "ZAM_GRN_BAG_CONDITION_STATUS",
                "RECEIVING WAREHOUSE": "GRN_WAREHOUSE_NAME",
                "RECEIVING HORSE REGISTRATION": "GRN_TRUCK_REG",
                "Added Email ID": "WITNESS_GRN_USER",
                "Added Time": "GRN_FORM_COMPLETE"
            }

            # Create final DataFrame for download
            mapped_df_for_download = filtered_df.rename(columns=column_mappings)
            for col in column_mappings.values():
                if col not in mapped_df_for_download.columns:
                    mapped_df_for_download[col] = None
            mapped_df_for_download = mapped_df_for_download[column_mappings.values()]

            st.write(f"Total Filtered Entries: {len(mapped_df_for_download)}")
            st.write("Mapped DataFrame for Download:")
            st.dataframe(mapped_df_for_download)

            # Define the filename based on start and end date-time selections
            file_name = f"From_{start_date.strftime('%Y%m%d')}_{start_time.strftime('%H%M')}_to_{end_date.strftime('%Y%m%d')}_{end_time.strftime('%H%M')}_Receiving.csv"

            # Convert filtered data to CSV for download
            csv_data = mapped_df_for_download.to_csv(index=False)
            st.download_button(
                label="Download Filtered Combined Data as CSV",
                data=csv_data,
                file_name=file_name,
                mime="text/csv"
            )

        else:
            st.error("The file does not contain the required column: 'BAG ID.'")
    except Exception as e:
        st.error(f"Error processing file: {e}")
