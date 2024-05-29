import os
import pyodbc
import pandas as pd
import streamlit as st
from datetime import datetime
import base64
import io
import time
import pytz
from multiprocessing import Pool

# Set page configuration
st.set_page_config(layout="wide")

# Database connection parameters
server = '61.91.59.134'
port = '1544'
database = 'KGETEST'
db_username = 'sa'
db_password = 'kg@dm1nUsr!'
conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server},{port};DATABASE={database};UID={db_username};PWD={db_password}'

# Function to establish database connection
def establish_connection():
    return pyodbc.connect(conn_str)

# Function to load data from the database with caching
@st.cache(allow_output_mutation=True, hash_funcs={pyodbc.Connection: id})
def load_data(selected_product_name, selected_whcid, conn):
    query_detail = '''
    SELECT
        a.ITMID, a.NAME_TH, a.PURCHASING_UOM, a.MODEL, 
        b.BRAND_NAME, c.CAB_NAME, d.SHE_NAME, e.BLK_NAME,
        p.WHCID, w.NAME_TH AS WAREHOUSE_NAME, p.BATCH_NO, SUM(p.BALANCE) AS TOTAL_BALANCE
    FROM
        ERP_ITEM_MASTER_DATA a
        LEFT JOIN ERP_BRAND b ON a.BRAID = b.BRAID
        LEFT JOIN ERP_CABINET c ON a.CABID = c.CABID
        LEFT JOIN ERP_SHELF d ON a.SHEID = d.SHEID
        LEFT JOIN ERP_BLOCK e ON a.BLKID = e.BLKID
        LEFT JOIN ERP_GOODS_RECEIPT_PO_BATCH p ON a.ITMID = p.ITMID
        LEFT JOIN ERP_WAREHOUSES_CODE w ON p.WHCID = w.WHCID
    WHERE
        a.EDITDATE IS NULL AND
        a.GRPID IN ('11', '71', '77', '73', '76', '75') AND
        a.ITMID + ' - ' + a.NAME_TH + ' - ' + a.MODEL = ? AND
        p.WHCID = ?
    GROUP BY
        a.ITMID, a.NAME_TH, a.PURCHASING_UOM, a.MODEL, a.PHOTONAME,
        b.BRAND_NAME, c.CAB_NAME, d.SHE_NAME, e.BLK_NAME,
        p.WHCID, w.NAME_TH, p.BATCH_NO
    '''

    filtered_items_df = pd.read_sql(query_detail, conn, params=(selected_product_name, selected_whcid.split(' -')[0]))
    return filtered_items_df

# Function to save data to the database
def save_to_database(product_data, conn):
    try:
        query = '''
        INSERT INTO ERP_COUNT_STOCK (
            ID, LOGDATE, ENTERBY, ITMID, ITEMNAME, UNIT, REMARK, ACTUAL, INSTOCK
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        cursor = conn.cursor()
        cursor.execute("SELECT ISNULL(MAX(ID), 0) FROM ERP_COUNT_STOCK")
        max_id = cursor.fetchone()[0]
        new_id = max_id + 1

        data = [
            new_id,
            product_data['Login_Time'], product_data['Enter_By'], product_data['Product_ID'],
            product_data['Product_Name'], product_data['Purchasing_UOM'], product_data['Remark'],
            product_data['Total_Balance'], product_data['Quantity']
        ]
        cursor.execute(query, data)
        conn.commit()
        st.success("Data saved successfully!")
    except pyodbc.Error as e:
        st.error(f"Error inserting data: {e}")

# Function to check user credentials
def check_credentials(username, password):
    user_db = {
        'user1': 'password1',
        'user2': 'password2',
        'admin': 'adminpassword'
    }
    return user_db.get(username) == password
    
# Function to display the UI
def display_ui():
    if st.session_state.logged_in:
        st.write(f"👨🏻‍💼👩🏻‍💼 รายการสินค้าที่ {st.session_state.username} นับ")

        if st.session_state.selected_whcid is None:
            st.subheader("เลือก WHCID")
            with establish_connection() as conn:
                whcid_query = '''
                SELECT y.WHCID, y.NAME_TH
                FROM ERP_WAREHOUSES_CODE y
                WHERE y.EDITDATE IS NULL
                '''
                whcid_df = pd.read_sql(whcid_query, conn)
                selected_whcid = st.selectbox("เลือก WHCID:", options=whcid_df['WHCID'] + ' - ' + whcid_df['NAME_TH'])

                if st.button("👉 Enter WHCID"):
                    st.session_state.selected_whcid = selected_whcid
        else:
            st.write(f"คุณเลือก WHCID: {st.session_state.selected_whcid}")

            st.subheader("ค้นหาสินค้า")

            with establish_connection() as conn:
                product_query = '''
                SELECT x.ITMID, x.NAME_TH, x.MODEL, x.EDITDATE, q.BRAND_NAME
                FROM ERP_ITEM_MASTER_DATA x
                LEFT JOIN ERP_BRAND q ON x.BRAID = q.BRAID
                WHERE x.EDITDATE IS NULL AND x.GRPID IN ('11', '71', '77', '73', '76', '75')
                '''
                items_df = pd.read_sql(product_query, conn)

            items_options = [None] + list(items_df['ITMID'] + ' - ' + items_df['NAME_TH'] + ' - ' + items_df['MODEL'])
            selected_product_name = st.selectbox("เลือกสินค้า:", options=items_options, key='selected_product')

            if selected_product_name:
                selected_item = items_df[items_df['ITMID'] + ' - ' + items_df['NAME_TH'] + ' - ' + items_df['MODEL'] == selected_product_name]
                selected_brand_name = selected_item['BRAND_NAME'].iloc[0] if not selected_item.empty else ""
                st.write(f"คุณเลือกสินค้า: {selected_product_name} - {selected_brand_name}")

                filtered_items_df = load_data(selected_product_name, st.session_state.selected_whcid, conn)

                if not filtered_items_df.empty:
                    st.write("### รายละเอียดสินค้า:")
                    # Filtered DataFrame where TOTAL_BALANCE > 0
                    filtered_items_df_positive_balance = filtered_items_df[filtered_items_df['TOTAL_BALANCE'] > 0]

                    if not filtered_items_df_positive_balance.empty:
                        # Select the required columns to display
                            display_columns = [
                                'CAB_NAME', 'SHE_NAME', 'BLK_NAME',
                                'BATCH_NO', 'TOTAL_BALANCE'
                            ]
                            st.dataframe(filtered_items_df_positive_balance[display_columns])

                            total_balance = filtered_items_df_positive_balance['TOTAL_BALANCE'].sum()
                            st.write(f"รวมยอดสินค้าในคลัง: {total_balance}")

                            product_quantity = st.number_input(label='จำนวนสินค้า 🛒', min_value=0, value=st.session_state.product_quantity)
                            remark = st.text_area('Remark', value=st.session_state.remark)

                            if st.button('👉 Enter') and product_quantity > 0:
                                product_data = {
                                    'Login_Time': st.session_state.login_time,
                                    'Enter_By': st.session_state.username,
                                    'Product_ID': str(filtered_items_df['ITMID'].iloc[0]),
                                    'Product_Name': str(filtered_items_df['NAME_TH'].iloc[0]),
                                    'Model': str(filtered_items_df['MODEL'].iloc[0]),
                                    'Brand_Name': str(filtered_items_df['BRAND_NAME'].iloc[0]),
                                    'Cabinet': str(filtered_items_df['CAB_NAME'].iloc[0]),
                                    'Shelf': str(filtered_items_df['SHE_NAME'].iloc[0]),
                                    'Block': str(filtered_items_df['BLK_NAME'].iloc[0]),
                                    'Warehouse_ID': str(filtered_items_df['WHCID'].iloc[0]),
                                    'Warehouse_Name': str(filtered_items_df['WAREHOUSE_NAME'].iloc[0]),
                                    'Batch_No': str(filtered_items_df['BATCH_NO'].iloc[0]),
                                    'Purchasing_UOM': str(filtered_items_df['PURCHASING_UOM'].iloc[0]),
                                    'Total_Balance': int(total_balance),
                                    'Quantity': int(product_quantity),
                                    'Remark': remark
                                }
                                st.session_state.product_data.append(product_data)
                                save_to_database(product_data, conn)

                                if st.session_state.product_data:
                                    product_df = pd.DataFrame(st.session_state.product_data)
                                    download_data(product_df, st.session_state.username, st.session_state.login_time)

                                # Clear session state product data to prevent duplicates on next save
                                st.session_state.product_data = []
                                # Reset the input fields
                                st.session_state.product_quantity = 0
                                st.session_state.remark = ""

                    else:
                        st.write("ไม่มีสินค้าที่มียอดเหลือในคลัง")
                else:
                    st.warning("ไม่พบข้อมูลสินค้าที่เลือก")

            if st.button('📤 Logout'):
                st.session_state.logged_in = False
                st.session_state.username = ''
                st.session_state.department_name = ''
                st.session_state.login_time = ''
                st.session_state.selected_whcid = None
                st.session_state.selected_product_name = None
                st.session_state.product_data = []
                st.session_state.product_quantity = 0
                st.session_state.remark = ""

    else:
        st.write("## 👾👾 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user_info = check_credentials(username, password)
            if user_info is not None:
                st.session_state.logged_in = True
                st.session_state.username = username
                timezone = pytz.timezone('Asia/Bangkok')
                current_time = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.login_time = current_time
                st.success(f"🎉🎉 Welcome {username}")
                time.sleep(1)
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")

if __name__ == "__main__":
    display_ui()
