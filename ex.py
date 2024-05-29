import os
import pyodbc
import pandas as pd
import streamlit as st
from datetime import datetime
import base64
import io
import time
import pytz

# Set page configuration
st.set_page_config(layout="wide")

# Database connection parameters
server = '61.91.59.134'
port = '1544'
database = 'KGETEST'
db_username = 'sa'
db_password = 'kg@dm1nUsr!'
conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server},{port};DATABASE={database};UID={db_username};PWD={db_password}'

# Function to check user credentials
def check_credentials(username, password):
    user_db = {
        'user1': 'password1',
        'user2': 'password2',
        'admin': 'adminpassword'
    }
    return user_db.get(username) == password

# Function to create a download link for the data
def download_data(df, username, login_time):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    login_info = pd.DataFrame({
        'Username': [username],
        'Login Time': [login_time]
    })
    login_info.to_excel(writer, index=False, sheet_name='LoginInfo')

    df.to_excel(writer, index=False, sheet_name='ProductData')
    writer.close()
    processed_data = output.getvalue()

    b64 = base64.b64encode(processed_data).decode()
    today = datetime.today().strftime('%Y-%m-%d %H-%M-%S')
    filename = f"product_data_{username}_{today}.xlsx"

    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">🚚🛒🚛📂</a>'
    st.markdown(href, unsafe_allow_html=True)

# Function to save data to the database
def save_to_database(product_data):
    try:
        query = '''
        INSERT INTO ERP_COUNT_STOCK (
            ID, LOGDATE, ENTERBY, ITMID, ITEMNAME, UNIT, REMARK, ACTUAL, INSTOCK
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        with pyodbc.connect(conn_str) as conn:
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

def load_data(selected_product_name, selected_whcid):
    with pyodbc.connect(conn_str) as conn_detail:
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

        filtered_items_df = pd.read_sql(query_detail, conn_detail, params=(selected_product_name, selected_whcid.split(' -')[0]))
        return filtered_items_df

def login():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ''
        st.session_state.login_time = ''
        st.session_state.selected_whcid = None
        st.session_state.selected_product_name = None
        st.session_state.product_data = []
        st.session_state.product_quantity = 0
        st.session_state.remark = ""

    if st.session_state.logged_in:
        st.write(f"👨🏻‍💼👩🏻‍💼 รายการสินค้าที่ {st.session_state.username} นับ")
        
        # Add your code related to logged in users here

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
                current_time = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:S:%d:%d:%d):
                st.session_state.login_time = current_time
                st.success(f"🎉🎉 Welcome {username}")
                time.sleep(1)
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")

def select_product():
    st.subheader("เลือก WHCID")
    with pyodbc.connect(conn_str) as conn:
        whcid_query = '''
        SELECT y.WHCID, y.NAME_TH
        FROM ERP_WAREHOUSES_CODE y
        WHERE y.EDITDATE IS NULL
        '''
        whcid_df = pd.read_sql(whcid_query, conn)
        selected_whcid = st.selectbox("เลือก WHCID:", options=whcid_df['WHCID'] + ' - ' + whcid_df['NAME_TH'])

        if st.button("เลือก"):
            st.session_state.selected_whcid = selected_whcid
            st.experimental_rerun()

def select_product_name():
    st.subheader("เลือกสินค้า")
    product_names = load_product_names()
    selected_product_name = st.selectbox("เลือกสินค้า:", product_names)
    if st.button("เลือก"):
        st.session_state.selected_product_name = selected_product_name
        st.experimental_rerun()

def load_product_names():
    with pyodbc.connect(conn_str) as conn:
        query = '''
        SELECT DISTINCT ITMID + ' - ' + NAME_TH + ' - ' + MODEL AS ProductName
        FROM ERP_ITEM_MASTER_DATA
        WHERE EDITDATE IS NULL
        '''
        product_names_df = pd.read_sql(query, conn)
        return product_names_df['ProductName'].tolist()

def enter_quantity():
    st.subheader("จำนวนสินค้า")
    product_quantity = st.number_input(label='จำนวนสินค้า 🛒', min_value=0, value=st.session_state.product_quantity) 
    if st.button("บันทึก"):
        st.session_state.product_quantity = product_quantity
        st.experimental_rerun()

def enter_remark():
    st.subheader("หมายเหตุ")
    remark = st.text_input("ใส่หมายเหตุ (ถ้ามี)")
    if st.button("บันทึก"):
        st.session_state.remark = remark
        st.experimental_rerun()

def submit_count():
    if st.button("ส่งผลการนับ"):
        product_data = {
            'Login_Time': st.session_state.login_time,
            'Enter_By': st.session_state.username,
            'Product_ID': st.session_state.selected_product_name.split(' -')[0],
            'Product_Name': st.session_state.selected_product_name.split(' -')[1],
            'Purchasing_UOM': '',  # Add your code to get this information
            'Remark': st.session_state.remark,
            'Total_Balance': 0,  # Add your code to get this information
            'Quantity': st.session_state.product_quantity
        }
        save_to_database(product_data)
        st.session_state.product_quantity = 0
        st.session_state.remark = ""
        st.experimental_rerun()

def main():
    login()
    
    if st.session_state.logged_in:
        select_product()
        select_product_name()
        enter_quantity()
        enter_remark()
        submit_count()

if __name__ == "__main__":
    main()

