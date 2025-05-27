import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import base64

class ReportGenerator:
    """Utility class for generating reports in various formats."""
    
    @staticmethod
    def generate_excel_report(data, report_type="transactions", filename=None):
        """Generate Excel report from data."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type}_report_{timestamp}.xlsx"
        
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if report_type == "transactions":
                df = pd.DataFrame(data)
                if not df.empty:
                    # Convert date columns
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    if 'created_at' in df.columns:
                        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                df.to_excel(writer, sheet_name='Transactions', index=False)
            
            elif report_type == "summary":
                # Create multiple sheets for summary data
                if 'transactions' in data:
                    df_trans = pd.DataFrame(data['transactions'])
                    if not df_trans.empty:
                        df_trans.to_excel(writer, sheet_name='Transactions', index=False)
                
                if 'summary' in data:
                    df_summary = pd.DataFrame([data['summary']])
                    df_summary.to_excel(writer, sheet_name='Summary', index=False)
                
                if 'category_breakdown' in data:
                    df_categories = pd.DataFrame(data['category_breakdown'])
                    if not df_categories.empty:
                        df_categories.to_excel(writer, sheet_name='Categories', index=False)
        
        output.seek(0)
        return output, filename
    
    @staticmethod
    def generate_csv_report(data, filename=None):
        """Generate CSV report from data."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transactions_report_{timestamp}.csv"
        
        output = BytesIO()
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Convert date columns
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        csv_data = df.to_csv(index=False)
        output.write(csv_data.encode('utf-8'))
        output.seek(0)
        
        return output, filename
    
    @staticmethod
    def generate_pdf_report(data, report_type="transactions", filename=None):
        """Generate PDF report from data."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type}_report_{timestamp}.pdf"
        
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph(f"{report_type.title()} Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_para = Paragraph(f"Generated on: {date_str}", styles['Normal'])
        story.append(date_para)
        story.append(Spacer(1, 12))
        
        if report_type == "transactions" and data:
            # Create table
            df = pd.DataFrame(data)
            if not df.empty:
                # Select key columns for PDF
                columns = ['date', 'amount', 'type', 'category_name', 'note']
                available_columns = [col for col in columns if col in df.columns]
                
                if available_columns:
                    table_data = [available_columns]  # Headers
                    
                    for _, row in df.iterrows():
                        row_data = []
                        for col in available_columns:
                            value = row[col]
                            if col == 'date' and pd.notna(value):
                                value = pd.to_datetime(value).strftime('%Y-%m-%d')
                            elif col == 'amount':
                                value = f"${value:,.2f}"
                            elif pd.isna(value):
                                value = "-"
                            row_data.append(str(value))
                        table_data.append(row_data)
                    
                    table = Table(table_data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    
                    story.append(table)
        
        doc.build(story)
        output.seek(0)
        
        return output, filename
    
    @staticmethod
    def generate_chart_base64(data, chart_type="pie", title="Chart"):
        """Generate chart as base64 encoded string."""
        plt.figure(figsize=(10, 6))
        
        if chart_type == "pie" and data:
            labels = [item['category'] for item in data]
            sizes = [item['amount'] for item in data]
            
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            plt.title(title)
            
        elif chart_type == "bar" and data:
            categories = [item['category'] for item in data]
            amounts = [item['amount'] for item in data]
            
            plt.bar(categories, amounts)
            plt.title(title)
            plt.xticks(rotation=45)
            plt.ylabel('Amount')
            
        elif chart_type == "line" and data:
            dates = [item['date'] for item in data]
            amounts = [item['amount'] for item in data]
            
            plt.plot(dates, amounts, marker='o')
            plt.title(title)
            plt.xticks(rotation=45)
            plt.ylabel('Amount')
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return f"data:image/png;base64,{image_base64}"
    
    @staticmethod
    def generate_transactions_csv(transactions, user_id):
        """Generate CSV file for transactions."""
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transactions_{user_id}_{timestamp}.csv"
        file_path = os.path.join(temp_dir, filename)
        
        # Prepare data
        df = pd.DataFrame(transactions)
        if not df.empty:
            # Format date column
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # Remove internal fields
            columns_to_remove = ['_id', 'user_id']
            df = df.drop(columns=[col for col in columns_to_remove if col in df.columns])
            
            # Reorder columns
            column_order = ['date', 'category_name', 'type', 'amount', 'note']
            df = df.reindex(columns=[col for col in column_order if col in df.columns])
        
        # Save to file
        df.to_csv(file_path, index=False)
        return file_path
    
    @staticmethod
    def generate_transactions_excel(transactions, user_id):
        """Generate Excel file for transactions."""
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transactions_{user_id}_{timestamp}.xlsx"
        file_path = os.path.join(temp_dir, filename)
        
        # Prepare data
        df = pd.DataFrame(transactions)
        if not df.empty:
            # Format date column
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # Remove internal fields
            columns_to_remove = ['_id', 'user_id']
            df = df.drop(columns=[col for col in columns_to_remove if col in df.columns])
            
            # Reorder columns
            column_order = ['date', 'category_name', 'type', 'amount', 'note']
            df = df.reindex(columns=[col for col in column_order if col in df.columns])
        
        # Save to file
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Transactions', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Transactions']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        return file_path
    
    @staticmethod
    def generate_transactions_pdf(transactions, user_id):
        """Generate PDF file for transactions."""
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transactions_{user_id}_{timestamp}.pdf"
        file_path = os.path.join(temp_dir, filename)
        
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph("Transaction Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_para = Paragraph(f"Generated on: {date_str}", styles['Normal'])
        story.append(date_para)
        story.append(Spacer(1, 12))
        
        if transactions:
            # Summary
            total_income = sum(t['amount'] for t in transactions if t['type'] == 'income')
            total_expense = sum(t['amount'] for t in transactions if t['type'] == 'expense')
            balance = total_income - total_expense
            
            summary_para = Paragraph(f"Summary: {len(transactions)} transactions | Income: ${total_income:,.2f} | Expense: ${total_expense:,.2f} | Balance: ${balance:,.2f}", styles['Normal'])
            story.append(summary_para)
            story.append(Spacer(1, 12))
            
            # Create table
            table_data = [['Date', 'Category', 'Type', 'Amount', 'Note']]  # Headers
            
            for transaction in transactions:
                date_str = transaction.get('date', '')
                if isinstance(date_str, str):
                    try:
                        date_str = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    except:
                        pass
                
                row_data = [
                    str(date_str),
                    str(transaction.get('category_name', '')),
                    str(transaction.get('type', '')).title(),
                    f"${transaction.get('amount', 0):,.2f}",
                    str(transaction.get('note', '') or '-')
                ]
                table_data.append(row_data)
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(table)
        else:
            story.append(Paragraph("No transactions found.", styles['Normal']))
        
        doc.build(story)
        return file_path
    
    @staticmethod
    def generate_admin_csv_report(report_data):
        """Generate comprehensive CSV report for admin dashboard."""
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"admin_report_{timestamp}.csv"
        file_path = os.path.join(temp_dir, filename)
        
        output = BytesIO()
        
        # Create CSV content
        csv_content = []
        
        # System Overview
        csv_content.append("SYSTEM OVERVIEW")
        csv_content.append("================")
        system_stats = report_data.get('system_stats', {})
        csv_content.append(f"Total Users,{system_stats.get('total_users', 0)}")
        csv_content.append(f"Active Users,{system_stats.get('active_users', 0)}")
        csv_content.append(f"Total Transactions,{system_stats.get('transaction_count', 0)}")
        csv_content.append(f"Total Income,${system_stats.get('total_income', 0):,.2f}")
        csv_content.append(f"Total Expense,${system_stats.get('total_expense', 0):,.2f}")
        csv_content.append(f"Net Balance,${(system_stats.get('total_income', 0) - system_stats.get('total_expense', 0)):,.2f}")
        csv_content.append("")
        
        # Category Breakdown
        if 'categories' in report_data and report_data['categories']:
            csv_content.append("CATEGORY BREAKDOWN")
            csv_content.append("==================")
            csv_content.append("Category,Total Amount,Transaction Count,Percentage")
            
            total_expense = sum(cat['total'] for cat in report_data['categories'])
            for category in report_data['categories']:
                percentage = (category['total'] / total_expense * 100) if total_expense > 0 else 0
                csv_content.append(f"{category['_id']},${category['total']:,.2f},{category['count']},{percentage:.1f}%")
            csv_content.append("")
        
        # Monthly Trends
        if 'monthly_data' in report_data and report_data['monthly_data']:
            csv_content.append("MONTHLY TRENDS")
            csv_content.append("==============")
            csv_content.append("Year,Month,Type,Amount")
            
            for month_data in report_data['monthly_data']:
                year = month_data['_id']['year']
                month = month_data['_id']['month']
                trans_type = month_data['_id']['type']
                amount = month_data['total']
                csv_content.append(f"{year},{month:02d},{trans_type.title()},${amount:,.2f}")
            csv_content.append("")
        
        # User Activities
        if 'user_activities' in report_data and report_data['user_activities']:
            csv_content.append("TOP USER ACTIVITIES")
            csv_content.append("===================")
            csv_content.append("Username,Email,Total Income,Total Expense,Net Balance,Transaction Count")
            
            for activity in report_data['user_activities']:
                user_info = activity.get('user_info', {})
                username = user_info.get('username', 'Unknown')
                email = user_info.get('email', 'Unknown')
                income = activity.get('total_income', 0)
                expense = activity.get('total_expense', 0)
                balance = activity.get('net_balance', 0)
                count = activity.get('transaction_count', 0)
                csv_content.append(f"{username},{email},${income:,.2f},${expense:,.2f},${balance:,.2f},{count}")
            csv_content.append("")
        
        # Transaction Details
        if 'transactions' in report_data and report_data['transactions']:
            csv_content.append("TRANSACTION DETAILS")
            csv_content.append("===================")
            csv_content.append("Date,Username,Email,Category,Type,Amount,Note")
            
            for transaction in report_data['transactions'][:100]:  # Limit to first 100
                user_info = transaction.get('user_info', {})
                username = user_info.get('username', 'Unknown')
                email = user_info.get('email', 'Unknown')
                date = transaction.get('date', '')
                category = transaction.get('category_name', '')
                trans_type = transaction.get('type', '')
                amount = transaction.get('amount', 0)
                note = transaction.get('note', '').replace(',', ';')  # Replace commas to avoid CSV issues
                
                csv_content.append(f"{date},{username},{email},{category},{trans_type.title()},${amount:,.2f},{note}")
        
        # Write to BytesIO
        csv_data = "\n".join(csv_content)
        output.write(csv_data.encode('utf-8'))
        output.seek(0)
        
        return output, filename
    
    @staticmethod
    def generate_admin_excel_report(report_data):
        """Generate comprehensive Excel report for admin dashboard."""
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"admin_report_{timestamp}.xlsx"
        file_path = os.path.join(temp_dir, filename)
        
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # System Overview Sheet
            system_stats = report_data.get('system_stats', {})
            overview_data = {
                'Metric': ['Total Users', 'Active Users', 'Total Transactions', 'Total Income', 'Total Expense', 'Net Balance'],
                'Value': [
                    system_stats.get('total_users', 0),
                    system_stats.get('active_users', 0),
                    system_stats.get('transaction_count', 0),
                    f"${system_stats.get('total_income', 0):,.2f}",
                    f"${system_stats.get('total_expense', 0):,.2f}",
                    f"${(system_stats.get('total_income', 0) - system_stats.get('total_expense', 0)):,.2f}"
                ]
            }
            df_overview = pd.DataFrame(overview_data)
            df_overview.to_excel(writer, sheet_name='System Overview', index=False)
            
            # Category Breakdown Sheet
            if 'categories' in report_data and report_data['categories']:
                categories_data = []
                total_expense = sum(cat['total'] for cat in report_data['categories'])
                
                for category in report_data['categories']:
                    percentage = (category['total'] / total_expense * 100) if total_expense > 0 else 0
                    categories_data.append({
                        'Category': category['_id'],
                        'Total Amount': category['total'],
                        'Transaction Count': category['count'],
                        'Percentage': f"{percentage:.1f}%"
                    })
                
                df_categories = pd.DataFrame(categories_data)
                df_categories.to_excel(writer, sheet_name='Category Breakdown', index=False)
            
            # Monthly Trends Sheet
            if 'monthly_data' in report_data and report_data['monthly_data']:
                monthly_data = []
                for month_data in report_data['monthly_data']:
                    monthly_data.append({
                        'Year': month_data['_id']['year'],
                        'Month': month_data['_id']['month'],
                        'Type': month_data['_id']['type'].title(),
                        'Amount': month_data['total']
                    })
                
                df_monthly = pd.DataFrame(monthly_data)
                df_monthly.to_excel(writer, sheet_name='Monthly Trends', index=False)
            
            # User Activities Sheet
            if 'user_activities' in report_data and report_data['user_activities']:
                activities_data = []
                for activity in report_data['user_activities']:
                    user_info = activity.get('user_info', {})
                    activities_data.append({
                        'Username': user_info.get('username', 'Unknown'),
                        'Email': user_info.get('email', 'Unknown'),
                        'Total Income': activity.get('total_income', 0),
                        'Total Expense': activity.get('total_expense', 0),
                        'Net Balance': activity.get('net_balance', 0),
                        'Transaction Count': activity.get('transaction_count', 0)
                    })
                
                df_activities = pd.DataFrame(activities_data)
                df_activities.to_excel(writer, sheet_name='User Activities', index=False)
            
            # Transaction Details Sheet (limited to 1000 records)
            if 'transactions' in report_data and report_data['transactions']:
                transactions_data = []
                for transaction in report_data['transactions'][:1000]:
                    user_info = transaction.get('user_info', {})
                    transactions_data.append({
                        'Date': transaction.get('date', ''),
                        'Username': user_info.get('username', 'Unknown'),
                        'Email': user_info.get('email', 'Unknown'),
                        'Category': transaction.get('category_name', ''),
                        'Type': transaction.get('type', '').title(),
                        'Amount': transaction.get('amount', 0),
                        'Note': transaction.get('note', '')
                    })
                
                df_transactions = pd.DataFrame(transactions_data)
                df_transactions.to_excel(writer, sheet_name='Transaction Details', index=False)
        
        output.seek(0)
        return output, filename
    
    @staticmethod
    def generate_admin_pdf_report(report_data):
        """Generate comprehensive PDF report for admin dashboard."""
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"admin_report_{timestamp}.pdf"
        file_path = os.path.join(temp_dir, filename)
        
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph("Admin System Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_para = Paragraph(f"Generated on: {date_str}", styles['Normal'])
        story.append(date_para)
        story.append(Spacer(1, 20))
        
        # System Overview
        system_stats = report_data.get('system_stats', {})
        overview_title = Paragraph("System Overview", styles['Heading1'])
        story.append(overview_title)
        story.append(Spacer(1, 12))
        
        overview_data = [
            ['Metric', 'Value'],
            ['Total Users', str(system_stats.get('total_users', 0))],
            ['Active Users', str(system_stats.get('active_users', 0))],
            ['Total Transactions', str(system_stats.get('transaction_count', 0))],
            ['Total Income', f"${system_stats.get('total_income', 0):,.2f}"],
            ['Total Expense', f"${system_stats.get('total_expense', 0):,.2f}"],
            ['Net Balance', f"${(system_stats.get('total_income', 0) - system_stats.get('total_expense', 0)):,.2f}"]
        ]
        
        overview_table = Table(overview_data)
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(overview_table)
        story.append(Spacer(1, 20))
        
        # Top Categories
        if 'categories' in report_data and report_data['categories']:
            categories_title = Paragraph("Top Categories by Expense", styles['Heading1'])
            story.append(categories_title)
            story.append(Spacer(1, 12))
            
            categories_data = [['Category', 'Amount', 'Count', 'Percentage']]
            total_expense = sum(cat['total'] for cat in report_data['categories'])
            
            for category in report_data['categories'][:10]:  # Top 10
                percentage = (category['total'] / total_expense * 100) if total_expense > 0 else 0
                categories_data.append([
                    category['_id'],
                    f"${category['total']:,.2f}",
                    str(category['count']),
                    f"{percentage:.1f}%"
                ])
            
            categories_table = Table(categories_data)
            categories_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(categories_table)
            story.append(Spacer(1, 20))
        
        # Top Users
        if 'user_activities' in report_data and report_data['user_activities']:
            users_title = Paragraph("Top Active Users", styles['Heading1'])
            story.append(users_title)
            story.append(Spacer(1, 12))
            
            users_data = [['Username', 'Total Expense', 'Transaction Count', 'Net Balance']]
            
            for activity in report_data['user_activities'][:10]:  # Top 10
                user_info = activity.get('user_info', {})
                users_data.append([
                    user_info.get('username', 'Unknown'),
                    f"${activity.get('total_expense', 0):,.2f}",
                    str(activity.get('transaction_count', 0)),
                    f"${activity.get('net_balance', 0):,.2f}"
                ])
            
            users_table = Table(users_data)
            users_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(users_table)
