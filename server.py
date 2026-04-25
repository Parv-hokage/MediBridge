"""
Flask Web Server for MediBridge
Integrates the frontend with the SmartHealthcareExchange backend
"""

from flask import Flask, render_template, request, jsonify
from healthcare_system import SmartHealthcareExchange
import os

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='')

# Initialize healthcare exchange system globally
exchange = SmartHealthcareExchange()

def init_app_once(exchange_instance):
    """
    Safe Initialization (Fix for Double Boot):
    Flask's development server (with debug=True) uses a reloader. It starts a master process,
    which then spawns a duplicate worker process. If heavy initialization (like loading 10k rows)
    is placed at the module level, it runs twice—freezing the system. 
    By checking WERKZEUG_RUN_MAIN, we ensure data only loads exactly once.
    """
    csv_file = 'hospital_data_10000.csv'
    if os.path.exists(csv_file):
        print(f"Loading data from {csv_file}...")
        exchange_instance.load_data_from_csv(csv_file)
    else:
        print(f"CSV file '{csv_file}' not found. Falling back to small sample data...")
        exchange_instance.seed_sample_data()

# Only run the heavy initialization in the main worker process
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not os.environ.get("FLASK_DEBUG", "0") == "1":
    init_app_once(exchange)

# ==========================================
# PAGE ROUTES (MULTI-PAGE UI)
# ==========================================

@app.route('/')
def index():
    """Serve the Home page"""
    return render_template('index.html')

@app.route('/services')
def services():
    """Serve the Services feature page"""
    return render_template('services.html')

@app.route('/search')
def search_page():
    """Serve the Main Search UI"""
    return render_template('search.html')

@app.route('/contact')
def contact():
    """Serve the Contact page"""
    return render_template('contact.html')

# ==========================================
# API ROUTES
# ==========================================

@app.route('/api/search', methods=['POST'])
def search_medicines():
    """
    API endpoint for searching medicines with Server-Side Pagination.
    """
    try:
        data = request.get_json()
        
        hospital_id = data.get('hospital_id')
        item_code = data.get('item_code')
        sort_by = data.get('sort_by', 'smart')
        
        # Pagination parameters
        page = int(data.get('page', 1))
        limit = int(data.get('limit', 10))
        
        # Validation
        if not hospital_id or not item_code:
            return jsonify({'results': [], 'error': 'Missing hospital_id or item_code'}), 400
        
        # Check if hospital exists
        requester = exchange.get_hospital_by_id(hospital_id)
        if not requester:
            return jsonify({'results': [], 'error': f'Hospital with ID {hospital_id} not found'}), 404
        
        # Check if item exists
        item = exchange.get_item_by_code(item_code)
        if not item:
            return jsonify({'results': [], 'error': f'Medicine with code {item_code} not found'}), 404
        
        # Determine Data Source based on Pagination Page
        if page == 1:
            # Case A: First load (Fast Response using nearest cache)
            initial_results = exchange.get_initial_results(item_code, hospital_id)
            
            # ALSO compute full results (but don’t use for display)
            full_results = exchange.get_top_hospitals_by_time(item_code, hospital_id, N=100, K=50)
            
            # This guarantees accurate total across all pages!
            total_results = len(full_results)
            
            if not initial_results:
                results = []
            else:
                results = exchange.sort_hospitals(initial_results, sort_by)
                
        else:
            # Case B: Load More (Deep Fetch for Top 50 refined matches)
            full_results = exchange.get_top_hospitals_by_time(item_code, hospital_id, N=100, K=50)
            results = exchange.sort_hospitals(full_results, sort_by)
            total_results = len(results)
            
        # Apply Server-Side Pagination Algorithm on the Correct Data
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
            
        paginated_results = results[start_idx:end_idx]
        
        # Convert Hospital objects to dicts for JSON serialization
        serialized_results = []
        for result in paginated_results:
            serialized_results.append({
                'hospital': {
                    'id': result['hospital'].id,
                    'name': result['hospital'].name,
                    'city': result['hospital'].city,
                    'state': result['hospital'].state,
                    'contact': result['hospital'].contact
                },
                'quantity': result['quantity'],
                'price': result['price'],
                'delivery_time': result['delivery_time'],
                'distance': result['distance']
            })
        
        return jsonify({
            'results': serialized_results,
            'error': None,
            'medicine': item.name,
            'sort_by': sort_by,
            'total': total_results,
            'page': page,
            'limit': limit
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'results': [], 'error': f'Server error: {str(e)}'}), 500

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    try:
        hospitals = []
        for hospital in exchange.hospitals:
            hospitals.append({
                'id': hospital.id,
                'name': hospital.name,
                'city': hospital.city,
                'state': hospital.state,
                'contact': hospital.contact,
                'lat': hospital.lat,
                'lon': hospital.lon
            })
        return jsonify({'hospitals': hospitals, 'count': len(hospitals)})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/medicines', methods=['GET'])
def get_medicines():
    try:
        medicines = []
        for item in exchange.items:
            medicines.append({'code': item.code, 'name': item.name})
        return jsonify({'medicines': medicines, 'count': len(medicines)})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = {
            'total_hospitals': len(exchange.hospitals),
            'total_medicines': len(exchange.items),
            'total_inventory_records': len(exchange.inventory_records),
            'hospitals_by_state': {}
        }
        for hospital in exchange.hospitals:
            state = hospital.state
            stats['hospitals_by_state'][state] = stats['hospitals_by_state'].get(state, 0) + 1
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("MediBridge - Urban-Rural Medicine Connect")
    print("=" * 80)
    print("\nStarting Flask web server...")
    print("\nServer running at: http://localhost:5000")
    print("Open in browser: http://localhost:5000/")
    print("\nAPI Endpoints:")
    print("  POST /api/search          - Search for medicines (Paginated)")
    print("  GET  /api/hospitals       - Get all hospitals")
    print("  GET  /api/medicines       - Get all medicines")
    print("  GET  /api/stats           - Get system statistics")
    print("\n" + "=" * 80 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=5000)
