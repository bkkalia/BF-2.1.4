"""
BlackForest Portal Filter Dashboard
Modern web-based dashboard for tender data analysis and filtering
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime, timedelta
import csv
import io
from collections import defaultdict, Counter

app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'blackforest_tenders.sqlite3')

def get_db_connection():
    """Get a SQLite database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def format_currency(amount):
    """Format currency for display"""
    if amount is None:
        return "-"
    try:
        amount = float(amount)
        if amount >= 1e7:  # Crore
            return f"₹{amount/1e7:.2f} Cr"
        elif amount >= 1e5:  # Lakh
            return f"₹{amount/1e5:.2f} L"
        elif amount >= 1e3:  # Thousand
            return f"₹{amount/1e3:.2f} K"
        return f"₹{amount:.2f}"
    except (ValueError, TypeError):
        return "-"

def format_date(date_str):
    """Format date for display"""
    if not date_str:
        return "-"
    try:
        date_obj = datetime.strptime(date_str.split(' ')[0], '%Y-%m-%d')
        return date_obj.strftime('%d-%m-%Y')
    except:
        return "-"

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/portals')
def get_portals():
    """Get list of available portals"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT portal_slug, portal_code, portal_name, is_active
            FROM portals
            ORDER BY portal_name
        """)
        portals = []
        for row in cursor.fetchall():
            portals.append({
                'slug': row['portal_slug'],
                'code': row['portal_code'],
                'name': row['portal_name'],
                'active': bool(row['is_active'])
            })
        conn.close()
        return jsonify({'success': True, 'data': portals})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/states')
def get_states():
    """Get list of states from tender data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT state_name, state_code
            FROM tender_items
            WHERE state_name IS NOT NULL AND state_name != ''
            ORDER BY state_name
        """)
        states = []
        for row in cursor.fetchall():
            states.append({
                'name': row['state_name'],
                'code': row['state_code']
            })
        conn.close()
        return jsonify({'success': True, 'data': states})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/districts')
def get_districts():
    """Get list of districts for a specific state"""
    state_name = request.args.get('state')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if state_name:
            cursor.execute("""
                SELECT DISTINCT district
                FROM tender_items
                WHERE district IS NOT NULL AND district != '' AND state_name = ?
                ORDER BY district
            """, (state_name,))
        else:
            cursor.execute("""
                SELECT DISTINCT district
                FROM tender_items
                WHERE district IS NOT NULL AND district != ''
                ORDER BY district
            """)
        districts = []
        for row in cursor.fetchall():
            if row['district']:
                districts.append(row['district'])
        conn.close()
        return jsonify({'success': True, 'data': districts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cities')
def get_cities():
    """Get list of cities for a specific district and state"""
    district = request.args.get('district')
    state_name = request.args.get('state')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if district and state_name:
            cursor.execute("""
                SELECT DISTINCT city
                FROM tender_items
                WHERE city IS NOT NULL AND city != '' AND district = ? AND state_name = ?
                ORDER BY city
            """, (district, state_name))
        elif district:
            cursor.execute("""
                SELECT DISTINCT city
                FROM tender_items
                WHERE city IS NOT NULL AND city != '' AND district = ?
                ORDER BY city
            """, (district,))
        elif state_name:
            cursor.execute("""
                SELECT DISTINCT city
                FROM tender_items
                WHERE city IS NOT NULL AND city != '' AND state_name = ?
                ORDER BY city
            """, (state_name,))
        else:
            cursor.execute("""
                SELECT DISTINCT city
                FROM tender_items
                WHERE city IS NOT NULL AND city != ''
                ORDER BY city
            """)
        cities = []
        for row in cursor.fetchall():
            if row['city']:
                cities.append(row['city'])
        conn.close()
        return jsonify({'success': True, 'data': cities})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tender_types')
def get_tender_types():
    """Get list of tender types"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT tender_type
            FROM tender_items
            WHERE tender_type IS NOT NULL AND tender_type != ''
            ORDER BY tender_type
        """)
        tender_types = []
        for row in cursor.fetchall():
            if row['tender_type']:
                tender_types.append(row['tender_type'])
        conn.close()
        return jsonify({'success': True, 'data': tender_types})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/work_types')
def get_work_types():
    """Get list of work types"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT work_type
            FROM tender_items
            WHERE work_type IS NOT NULL AND work_type != ''
            ORDER BY work_type
        """)
        work_types = []
        for row in cursor.fetchall():
            if row['work_type']:
                work_types.append(row['work_type'])
        conn.close()
        return jsonify({'success': True, 'data': work_types})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/kpis')
def get_kpis():
    """Get key performance indicators"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total tenders
        cursor.execute("SELECT COUNT(*) as count FROM tender_items")
        total_tenders = cursor.fetchone()['count']
        
        # Live tenders
        cursor.execute("SELECT COUNT(*) as count FROM tender_items WHERE is_live = 1")
        live_tenders = cursor.fetchone()['count']
        
        # Total estimated value
        cursor.execute("SELECT SUM(estimated_cost_value) as total FROM tender_items WHERE estimated_cost_value > 0")
        total_value = cursor.fetchone()['total']
        
        # Average tender value
        cursor.execute("SELECT AVG(estimated_cost_value) as avg FROM tender_items WHERE estimated_cost_value > 0")
        avg_value = cursor.fetchone()['avg']
        
        # Tenders by status
        cursor.execute("""
            SELECT tender_status, COUNT(*) as count
            FROM tender_items
            GROUP BY tender_status
        """)
        status_dist = []
        for row in cursor.fetchall():
            status_dist.append({
                'status': row['tender_status'],
                'count': row['count']
            })
        
        # Tenders by portal
        cursor.execute("""
            SELECT p.portal_name, COUNT(*) as count
            FROM tender_items ti
            JOIN portals p ON ti.portal_id = p.id
            GROUP BY p.portal_name
            ORDER BY count DESC
            LIMIT 10
        """)
        portal_dist = []
        for row in cursor.fetchall():
            portal_dist.append({
                'portal': row['portal_name'],
                'count': row['count']
            })
        
        # Tenders by state
        cursor.execute("""
            SELECT state_name, COUNT(*) as count
            FROM tender_items
            WHERE state_name IS NOT NULL AND state_name != ''
            GROUP BY state_name
            ORDER BY count DESC
            LIMIT 10
        """)
        state_dist = []
        for row in cursor.fetchall():
            state_dist.append({
                'state': row['state_name'],
                'count': row['count']
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_tenders': total_tenders,
                'live_tenders': live_tenders,
                'total_value': format_currency(total_value),
                'avg_value': format_currency(avg_value),
                'status_distribution': status_dist,
                'portal_distribution': portal_dist,
                'state_distribution': state_dist
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tenders/search', methods=['POST'])
def search_tenders():
    """Search and filter tenders"""
    try:
        data = request.get_json()
        
        # Build query
        query = """
            SELECT 
                ti.id,
                p.portal_name,
                ti.tender_id_extracted,
                ti.title_ref,
                ti.department_name,
                ti.published_at,
                ti.opening_at,
                ti.closing_at,
                ti.estimated_cost_value,
                ti.emd_amount_value,
                ti.tender_status,
                ti.state_name,
                ti.district,
                ti.city
            FROM tender_items ti
            JOIN portals p ON ti.portal_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Apply filters
        if data.get('portal') and data['portal'] != 'All':
            query += " AND p.portal_slug = ?"
            params.append(data['portal'])
        
        if data.get('status') and data['status'] != 'All':
            if data['status'] == 'Live':
                query += " AND ti.is_live = 1"
            elif data['status'] == 'Archived':
                query += " AND ti.is_live = 0"
            else:
                query += " AND ti.tender_status = ?"
                params.append(data['status'])
        
        if data.get('state') and data['state'] != 'All':
            query += " AND ti.state_name = ?"
            params.append(data['state'])
        
        if data.get('district') and data['district'] != 'All':
            query += " AND ti.district = ?"
            params.append(data['district'])
        
        if data.get('city') and data['city'] != 'All':
            query += " AND ti.city = ?"
            params.append(data['city'])
        
        if data.get('tender_type') and data['tender_type'] != 'All':
            query += " AND ti.tender_type = ?"
            params.append(data['tender_type'])
        
        if data.get('work_type') and data['work_type'] != 'All':
            query += " AND ti.work_type = ?"
            params.append(data['work_type'])
        
        # Date filters
        if data.get('from_date'):
            query += " AND ti.published_at >= ?"
            params.append(data['from_date'] + ' 00:00:00')
        
        if data.get('to_date'):
            query += " AND ti.published_at <= ?"
            params.append(data['to_date'] + ' 23:59:59')
        
        # Amount filters
        if data.get('min_amount'):
            query += " AND ti.estimated_cost_value >= ?"
            params.append(float(data['min_amount']))
        
        if data.get('max_amount'):
            query += " AND ti.estimated_cost_value <= ?"
            params.append(float(data['max_amount']))
        
        # Search query
        if data.get('search_query'):
            query += """ AND (
                ti.title_ref LIKE ? OR 
                ti.department_name LIKE ? OR 
                ti.tender_id_extracted LIKE ? OR
                ti.organization_chain LIKE ?
            )"""
            search_term = f"%{data['search_query']}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        # Sorting
        sort_by = data.get('sort_by', 'published_at')
        sort_order = data.get('sort_order', 'desc')
        
        valid_sort_fields = ['published_at', 'closing_at', 'estimated_cost_value', 'portal_name', 'department_name']
        if sort_by not in valid_sort_fields:
            sort_by = 'published_at'
        
        query += f" ORDER BY {sort_by} {sort_order}"
        
        # Pagination
        page = data.get('page', 1)
        page_size = data.get('page_size', 25)
        offset = (page - 1) * page_size
        query += " LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        # Execute query
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        tenders = cursor.fetchall()
        
        # Get total count for pagination
        count_query = query.split('ORDER BY')[0].replace(
            """
            SELECT 
                ti.id,
                p.portal_name,
                ti.tender_id_extracted,
                ti.title_ref,
                ti.department_name,
                ti.published_at,
                ti.opening_at,
                ti.closing_at,
                ti.estimated_cost_value,
                ti.emd_amount_value,
                ti.tender_status,
                ti.state_name,
                ti.district,
                ti.city
            """,
            "SELECT COUNT(*) as count"
        ).rsplit('LIMIT', 1)[0]
        
        count_params = params[:-2]  # Remove LIMIT and OFFSET params
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()['count']
        
        conn.close()
        
        # Format results
        formatted_tenders = []
        for row in tenders:
            formatted_tenders.append({
                'id': row['id'],
                'portal': row['portal_name'],
                'tender_id': row['tender_id_extracted'],
                'title': row['title_ref'],
                'department': row['department_name'],
                'published_at': format_date(row['published_at']),
                'opening_at': format_date(row['opening_at']),
                'closing_at': format_date(row['closing_at']),
                'estimated_cost': format_currency(row['estimated_cost_value']),
                'emd_amount': format_currency(row['emd_amount_value']),
                'status': row['tender_status'],
                'state': row['state_name'],
                'district': row['district'],
                'city': row['city'],
                'estimated_cost_raw': row['estimated_cost_value']
            })
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        return jsonify({
            'success': True,
            'data': {
                'tenders': formatted_tenders,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tenders/export', methods=['POST'])
def export_tenders():
    """Export filtered tenders to CSV"""
    try:
        data = request.get_json()
        
        # Build export query
        query = """
            SELECT 
                p.portal_name,
                ti.tender_id_extracted,
                ti.title_ref,
                ti.department_name,
                ti.organization_chain,
                ti.published_at,
                ti.opening_at,
                ti.closing_at,
                ti.estimated_cost_value,
                ti.emd_amount_value,
                ti.tender_status,
                ti.tender_type,
                ti.work_type,
                ti.state_name,
                ti.district,
                ti.city
            FROM tender_items ti
            JOIN portals p ON ti.portal_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Apply same filters as search
        if data.get('portal') and data['portal'] != 'All':
            query += " AND p.portal_slug = ?"
            params.append(data['portal'])
        
        if data.get('status') and data['status'] != 'All':
            if data['status'] == 'Live':
                query += " AND ti.is_live = 1"
            elif data['status'] == 'Archived':
                query += " AND ti.is_live = 0"
            else:
                query += " AND ti.tender_status = ?"
                params.append(data['status'])
        
        if data.get('state') and data['state'] != 'All':
            query += " AND ti.state_name = ?"
            params.append(data['state'])
        
        if data.get('district') and data['district'] != 'All':
            query += " AND ti.district = ?"
            params.append(data['district'])
        
        if data.get('city') and data['city'] != 'All':
            query += " AND ti.city = ?"
            params.append(data['city'])
        
        if data.get('tender_type') and data['tender_type'] != 'All':
            query += " AND ti.tender_type = ?"
            params.append(data['tender_type'])
        
        if data.get('work_type') and data['work_type'] != 'All':
            query += " AND ti.work_type = ?"
            params.append(data['work_type'])
        
        if data.get('from_date'):
            query += " AND ti.published_at >= ?"
            params.append(data['from_date'] + ' 00:00:00')
        
        if data.get('to_date'):
            query += " AND ti.published_at <= ?"
            params.append(data['to_date'] + ' 23:59:59')
        
        if data.get('min_amount'):
            query += " AND ti.estimated_cost_value >= ?"
            params.append(float(data['min_amount']))
        
        if data.get('max_amount'):
            query += " AND ti.estimated_cost_value <= ?"
            params.append(float(data['max_amount']))
        
        if data.get('search_query'):
            query += """ AND (
                ti.title_ref LIKE ? OR 
                ti.department_name LIKE ? OR 
                ti.tender_id_extracted LIKE ? OR
                ti.organization_chain LIKE ?
            )"""
            search_term = f"%{data['search_query']}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        query += " ORDER BY ti.published_at DESC"
        
        # Execute query
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        tenders = cursor.fetchall()
        conn.close()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Portal', 'Tender ID', 'Title', 'Department', 'Organization Chain',
            'Published Date', 'Opening Date', 'Closing Date', 'Estimated Cost',
            'EMD Amount', 'Status', 'Tender Type', 'Work Type', 'State', 'District', 'City'
        ])
        
        # Data rows
        for row in tenders:
            writer.writerow([
                row['portal_name'],
                row['tender_id_extracted'],
                row['title_ref'],
                row['department_name'],
                row['organization_chain'],
                format_date(row['published_at']),
                format_date(row['opening_at']),
                format_date(row['closing_at']),
                row['estimated_cost_value'],
                row['emd_amount_value'],
                row['tender_status'],
                row['tender_type'],
                row['work_type'],
                row['state_name'],
                row['district'],
                row['city']
            ])
        
        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'tenders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)