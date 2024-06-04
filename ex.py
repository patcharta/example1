import pyodbc
import pandas as pd
import streamlit as st
from datetime import datetime
import time
import pytz

# Set page configuration
st.set_page_config(layout="wide")

# Function to check user credentials
@st.cache_data
def check_credentials(username, password, conn_str):
    with pyodbc.connect(conn_str) as conn:
        query = '''
        SELECT f.USERNAME, f.PASSWORD
        FROM ERP_USERNAME f
        '''
        df = pd.read_sql(query, conn)

        user_record = df[df['USERNAME'] == username]
        if not user_record.empty and user_record.iloc[0]['PASSWORD'] == password:
            return True
        else:
            return False

@st.cache_data
def get_server_details(company):
    if company == 'K.G. Corporation Co.,Ltd.':
        return {
            'server': '61.91.59.134',
            'port': '1544', 
            'db_username': 'sa',
            'db_password': 'kg@dm1nUsr!',
            'database': 'KGETEST'
        }
    elif company == 'The Chill Resort & Spa Co., Ltd.':
        return {
            'server': '61.91.59.134',
            'port': '1544',
            'db_username': 'sa',
            'db_password': 'kg@dm1nUsr!',
            'database': 'THECHILL'
        }
    return None

@st.cache_data
def get_connection_string(company):
    details = get_server_details(company)
    if details:
        server = details['server']
        port = details['port']
        database = details['database']
        db_username = details['db_username']
        db_password = details['db_password']
        return f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server},{port};DATABASE={database};UID={db_username};PWD={db_password}'
    return None

def save_to_database(product_data, conn_str):
    try:
        remark = product_data.get('Remark', '')
        query = '''
        INSERT INTO ERP_COUNT_STOCK (
            ID, LOGDATE, ENTERBY, ITMID, ITEMNAME, UNIT, REMARK, ACTUAL, INSTOCK, WHCID
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ISNULL(MAX(ID), 0) FROM ERP_COUNT_STOCK")
            max_id = cursor.fetchone()[0]
            new_id = max_id + 1
            data = [
                new_id, product_data['Time'], product_data['Enter_By'], 
                product_data['Product_ID'], product_data['Product_Name'], 
                product_data['Purchasing_UOM'], remark, 
                product_data['Quantity'], product_data['Total_Balance'], product_data['whcid']
            ]
            cursor.execute(query, data)
            conn.commit()
        st.success("Data saved successfully!")
    except pyodbc.Error as e:
        st.error(f"Error inserting data: {e}")

@st.cache_data
def load_data(selected_product_name, selected_whcid, conn_str):
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
        a.ITMID, a.NAME_TH, a.PURCHASING_UOM, a.MODEL, 
        b.BRAND_NAME, c.CAB_NAME, d.SHE_NAME, e.BLK_NAME,
        p.WHCID, w.NAME_TH, p.BATCH_NO
    ORDER BY p.LOGDATE DESC, p.ITMID DESC
    '''
    with pyodbc.connect(conn_str) as conn:
        filtered_items_df = pd.read_sql(query_detail, conn, params=(selected_product_name, selected_whcid.split(' -')[0]))
    return filtered_items_df

@st.cache_data
def fetch_products(company):
    conn_str = get_connection_string(company)
    with pyodbc.connect(conn_str) as conn:
        product_query = '''
        SELECT x.ITMID, x.NAME_TH, x.MODEL, x.EDITDATE, q.BRAND_NAME
        FROM ERP_ITEM_MASTER_DATA x
        LEFT JOIN ERP_BRAND q ON x.BRAID = q.BRAID
        WHERE x.EDITDATE IS NULL AND x.GRPID IN ('11', '71', '77', '73', '76', '75')
        '''
        items_df = pd.read_sql(product_query, conn)
    return items_df.fillna('')

def select_product(company):
    st.subheader("ค้นหาสินค้า")
    items_df = fetch_products(company)
    items_options = [None] + list(items_df['ITMID'] + ' - ' + items_df['NAME_TH'] + ' - ' + items_df['MODEL'])
    selected_product_name = st.selectbox("เลือกสินค้า:", options=items_options, key='selected_product')

    if selected_product_name:
        selected_item = items_df[items_df['ITMID'] + ' - ' + items_df['NAME_TH'] + ' - ' + items_df['MODEL'] == selected_product_name]
        selected_brand_name = selected_item['BRAND_NAME'].iloc[0] if not selected_item.empty else ""
        st.write(f"คุณเลือกสินค้า: {selected_product_name} - {selected_brand_name}")
        return selected_product_name, selected_item
    else:
        return None, None

def count_product(selected_product_name, selected_item, conn_str):
    filtered_items_df = load_data(selected_product_name, st.session_state.selected_whcid, conn_str)
    if not filtered_items_df.empty:
        filtered_items_df = filtered_items_df.sort_values(by=['LOGDATE', 'ITMID'], ascending=[False, False])
        st.write("### รายละเอียดสินค้า:")
        filtered_items_df_positive_balance = filtered_items_df[filtered_items_df['TOTAL_BALANCE'] > 0]
        if not filtered_items_df_positive_balance.empty:
            display_columns = ['CAB_NAME', 'SHE_NAME', 'BLK_NAME', 'BATCH_NO', 'TOTAL_BALANCE']
            st.dataframe(filtered_items_df_positive_balance[display_columns])
            total_balance = filtered_items_df_positive_balance['TOTAL_BALANCE'].sum()
            st.write(f"รวมยอดสินค้าในคลัง: {total_balance}")

            product_quantity = st.number_input(label='จำนวนสินค้า 🛒', min_value=0, value=st.session_state.product_quantity)
            remark = st.text_area('Remark', value=st.session_state.remark)
            if st.button('👉 Enter') and product_quantity > 0:
                timezone = pytz.timezone('Asia/Bangkok')
                current_time = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
                product_data = {
                    'Time': current_time,
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
                    'Remark': remark,
                    'whcid': filtered_items_df['WHCID'].iloc[0]
                }
                st.session_state.product_data.append(product_data)
                save_to_database(product_data, conn_str)
                st.session_state.product_data = []
                st.session_state.product_quantity = 0
                st.session_state.remark = ""
                time.sleep(2)
                del st.session_state['selected_product']
                st.experimental_rerun()
        else:
            st.write("ไม่มีสินค้าที่มียอดเหลือในคลัง")
    else:
        st.warning("ไม่พบข้อมูลสินค้าที่เลือก")

def login_section():
    st.write("## 👾👾 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    company_options = ['K.G. Corporation Co.,Ltd.', 'The Chill Resort & Spa Co., Ltd.']
    company = st.selectbox("Company", options=company_options)
    if st.button("Login"):
        # Set the selected company to the session state
        st.session_state.company = company
        # Get the connection string based on the selected company
        conn_str = get_connection_string(company)
        if check_credentials(username, password, conn_str):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success(f"🎉🎉 Welcome {username}")
            time.sleep(1)
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")


def main_section():
    st.write(f"👨🏻‍💼👩🏻‍💼 รายการสินค้าที่ {st.session_state.username} นับ")
    st.write(st.session_state.company)

    if st.session_state.selected_whcid is None:
        st.subheader("เลือก WHCID")
        conn_str = get_connection_string(st.session_state.company)
        with pyodbc.connect(conn_str) as conn:
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
        selected_product_name, selected_item = select_product(st.session_state.company)
        if selected_product_name:
            conn_str = get_connection_string(st.session_state.company)
            count_product(selected_product_name, selected_item, conn_str)
        if st.button('📤 Logout'):
            st.session_state.logged_in = False
            st.session_state.username = ''
            st.session_state.selected_whcid = None
            st.session_state.selected_product_name = None
            st.session_state.product_data = []
            st.session_state.product_quantity = 0
            st.session_state.remark = ""

def app():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ''
        st.session_state.selected_whcid = None
        st.session_state.selected_product_name = None
        st.session_state.product_data = []
        st.session_state.product_quantity = 0
        st.session_state.remark = ""

    if st.session_state.logged_in:
        main_section()
    else:
        login_section()  

if __name__ == "__main__":
    app()


