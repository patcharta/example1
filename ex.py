import os
import pyodbc
import pandas as pd
import streamlit as st
from datetime import datetime
import base64
import io
import time

st.set_page_config(layout="wide")

server = '61.91.59.134'
port = '1544'
database = 'KGETEST'
db_username = 'sa'
db_password = 'kg@dm1nUsr!'
conn_str = f'DRIVER={{SQL Server}};SERVER={server},{port};DATABASE={database};UID={db_username};PWD={db_password}'

def check_credentials(username, password):
    user_db = {
        'user1': 'password1',
        'user2': 'password2',
        'admin': 'adminpassword'
    }
    return user_db.get(username) == password

def download_data(df, username, department_name, login_time, product_quantity):
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

def save_to_database(product_data_list):
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
            
            for product_data in product_data_list:
                data = [
                    new_id,  
                    product_data['Login_Time'], product_data['Enter_By'], product_data['Product_ID'], 
                    product_data['Product_Name'], product_data['Purchasing_UOM'], product_data['Remark'], 
                    product_data['Total_Balance'], product_data['Quantity']
                ]
                cursor.execute(query, data)
                new_id += 1
            conn.commit()
        st.success("Data saved successfully!")
    except pyodbc.Error as e:
        st.error(f"Error inserting data: {e}")

def app():
    if 'logged_in' not in st.session_state:
        st.image("https://media.tenor.com/Ybj4RpDI0moAAAAi/penguin-truck.gif")
        st.session_state.logged_in = False
        st.session_state.username = ''
        st.session_state.department_name = ''
        st.session_state.login_time = ''
        st.session_state.selected_whcid = None
        st.session_state.selected_product_name = None
        st.session_state.product_data = []  
        st.session_state.product_quantity = 0  

    if st.session_state.logged_in:
        st.write(f"👨🏻‍💼👩🏻‍💼 รายการสินค้าที่ {st.session_state.username} นับ")
        st.write(f"⛑️⛑️ แผนก: {st.session_state.department_name} ")

        if st.session_state.selected_whcid is None:
            st.subheader("เลือก WHCID")
            with pyodbc.connect(conn_str) as conn:
                whcid_query = '''
                SELECT y.WHCID, y.NAME_TH 
                FROM ERP_WAREHOUSES_CODE y
                '''
                whcid_df = pd.read_sql(whcid_query, conn)
                selected_whcid = st.selectbox("เลือก WHCID:", options=whcid_df['WHCID'] + ' - ' + whcid_df['NAME_TH'])
                
                if st.button("👉 Enter WHCID"):
                    st.session_state.selected_whcid = selected_whcid
        else:
            st.write(f"คุณเลือก WHCID: {st.session_state.selected_whcid}")

            st.subheader("ค้นหาสินค้า")
            
            with pyodbc.connect(conn_str) as conn:
                product_query = '''
                SELECT x.ITMID, x.NAME_TH, x.MODEL, x.EDITDATE
                FROM ERP_ITEM_MASTER_DATA x
                WHERE x.EDITDATE IS NULL AND x.GRPID IN ('11', '71', '77', '73', '76', '75')
                '''
                items_df = pd.read_sql(product_query, conn)
            
            selected_product_name = st.selectbox("เลือกสินค้า:", options=items_df['ITMID']  + ' - ' + items_df['NAME_TH'] + ' - ' + items_df['MODEL'], key='selected_product')
            st.session_state.selected_product_name = selected_product_name
            
            if selected_product_name:
                st.write(f"คุณเลือกสินค้า: {selected_product_name}")
                
                with pyodbc.connect(conn_str) as conn_detail:
                    query_detail = '''
                    SELECT 
                        a.ITMID, a.NAME_TH, a.PURCHASING_UOM, a.MODEL, a.PHOTONAME, 
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
                        a.GRPID IN ('11', '71', '77', '73', '76', '75') 
                        AND a.ITMID + ' - ' + a.NAME_TH + ' - ' + a.MODEL = ?
                        AND p.WHCID = ?
                    GROUP BY 
                        a.ITMID, a.NAME_TH, a.PURCHASING_UOM, a.MODEL, a.PHOTONAME, 
                        b.BRAND_NAME, c.CAB_NAME, d.SHE_NAME, e.BLK_NAME, 
                        p.WHCID, w.NAME_TH, p.BATCH_NO
                    '''
                    filtered_items_df = pd.read_sql(query_detail, conn_detail, params=(selected_product_name, st.session_state.selected_whcid.split(' - ')[0]))
            
                if not filtered_items_df.empty:
                    st.write("### รายละเอียดสินค้า:")
                    # Select the required columns to display
                    display_columns = [
                        'BRAND_NAME', 'CAB_NAME', 'SHE_NAME', 'BLK_NAME', 
                        'BATCH_NO', 'TOTAL_BALANCE'
                    ]
                    st.dataframe(filtered_items_df[display_columns])

                    total_balance = filtered_items_df['TOTAL_BALANCE'].sum()
                    if total_balance == 0:
                        st.write("ไม่มีสินค้า")
                    else:
                        st.write(f"รวมยอดสินค้าในคลัง: {total_balance}")
                        
                        product_quantity = st.session_state.product_quantity
                        product_quantity = st.number_input(label='จำนวนสินค้า 🛒', min_value=0, value=product_quantity)
                        remark = st.text_area('Remark')

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
                            save_to_database(st.session_state.product_data)
                            st.write(f"บันทึกข้อมูลสินค้า: {product_quantity} จำนวนสินค้า {st.session_state.selected_product_name}")

                            if st.session_state.product_data:
                                product_df = pd.DataFrame(st.session_state.product_data)
                                download_data(product_df, st.session_state.username, st.session_state.department_name, st.session_state.login_time, product_quantity)

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

    else:
        st.write("## 👾👾 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            user_info = check_credentials(username, password)
            if user_info is not None:
                st.session_state.logged_in = True
                st.session_state.username = username
                #st.session_state.department_name = user_info['DEPARTMENT_NAME']
                st.session_state.login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success(f"🎉🎉 Welcome {username}")
                time.sleep(1)
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")

if __name__ == "__main__":
    app()