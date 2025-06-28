from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import sqlite3
import hashlib
import json
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
CORS(app)

# California tax data - Enhanced with county-specific rates
CA_TAX_BRACKETS = [
    {"min": 0, "max": 10756, "rate": 0.01},
    {"min": 10756, "max": 25499, "rate": 0.02},
    {"min": 25499, "max": 40245, "rate": 0.04},
    {"min": 40245, "max": 55866, "rate": 0.06},
    {"min": 55866, "max": 70606, "rate": 0.08},
    {"min": 70606, "max": 360659, "rate": 0.093},
    {"min": 360659, "max": 432787, "rate": 0.103},
    {"min": 432787, "max": 721314, "rate": 0.113},
    {"min": 721314, "max": 1000000, "rate": 0.123},
    {"min": 1000000, "max": float('inf'), "rate": 0.133}
]

# County-specific additional tax rates (example data - you can update with actual CSV data)
COUNTY_TAX_RATES = {
    "Los Angeles": 0.0025,
    "San Francisco": 0.0038,
    "San Diego": 0.0015,
    "Orange": 0.0020,
    "Sacramento": 0.0018,
    "Riverside": 0.0012,
    "Alameda": 0.0028,
    "Santa Clara": 0.0035,
    "Fresno": 0.0015,
    "Kern": 0.0010,
    "San Bernardino": 0.0012,
    "Ventura": 0.0022,
    "Contra Costa": 0.0025,
    "Santa Barbara": 0.0020,
    "Solano": 0.0018
}

CA_STANDARD_DEDUCTION_SINGLE = 5540
CA_STANDARD_DEDUCTION_MARRIED = 11080
FEDERAL_STANDARD_DEDUCTION_SINGLE = 14600
FEDERAL_STANDARD_DEDUCTION_MARRIED = 29200

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect('budget_app.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create budget_profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            yearly_income REAL NOT NULL,
            filing_status TEXT DEFAULT 'single',
            county TEXT DEFAULT 'Los Angeles',
            housing_budget REAL,
            transportation_budget REAL,
            food_budget REAL,
            savings_budget REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create user_expenses table for tracking actual expenses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def calculate_ca_state_tax(income, filing_status='single'):
    """Calculate California state income tax"""
    deduction = CA_STANDARD_DEDUCTION_SINGLE if filing_status == 'single' else CA_STANDARD_DEDUCTION_MARRIED
    
    if income <= deduction:
        return 0
    
    taxable_income = income - deduction
    tax = 0
    
    for bracket in CA_TAX_BRACKETS:
        if taxable_income <= bracket["min"]:
            break
        
        bracket_income = min(taxable_income, bracket["max"]) - bracket["min"]
        tax += bracket_income * bracket["rate"]
    
    return tax

def calculate_federal_tax(income, filing_status='single'):
    """Calculate federal income tax"""
    federal_brackets_single = [
        {"min": 0, "max": 11000, "rate": 0.10},
        {"min": 11000, "max": 44725, "rate": 0.12},
        {"min": 44725, "max": 95375, "rate": 0.22},
        {"min": 95375, "max": 182050, "rate": 0.24},
        {"min": 182050, "max": 231250, "rate": 0.32},
        {"min": 231250, "max": 578125, "rate": 0.35},
        {"min": 578125, "max": float('inf'), "rate": 0.37}
    ]
    
    federal_brackets_married = [
        {"min": 0, "max": 22000, "rate": 0.10},
        {"min": 22000, "max": 89450, "rate": 0.12},
        {"min": 89450, "max": 190750, "rate": 0.22},
        {"min": 190750, "max": 364200, "rate": 0.24},
        {"min": 364200, "max": 462500, "rate": 0.32},
        {"min": 462500, "max": 693750, "rate": 0.35},
        {"min": 693750, "max": float('inf'), "rate": 0.37}
    ]
    
    brackets = federal_brackets_single if filing_status == 'single' else federal_brackets_married
    deduction = FEDERAL_STANDARD_DEDUCTION_SINGLE if filing_status == 'single' else FEDERAL_STANDARD_DEDUCTION_MARRIED
    
    if income <= deduction:
        return 0
    
    taxable_income = income - deduction
    tax = 0
    
    for bracket in brackets:
        if taxable_income <= bracket["min"]:
            break
        
        bracket_income = min(taxable_income, bracket["max"]) - bracket["min"]
        tax += bracket_income * bracket["rate"]
    
    return tax

def calculate_county_tax(income, county):
    """Calculate county-specific tax"""
    county_rate = COUNTY_TAX_RATES.get(county, 0.0015)  # Default rate if county not found
    return income * county_rate

def calculate_budget_breakdown(monthly_income, income_level='medium'):
    """Calculate recommended budget breakdown based on income level"""
    if monthly_income < 3000:  # Low income - more conservative
        return {
            "housing": monthly_income * 0.35,  # 35% for housing (higher due to CA costs)
            "transportation": monthly_income * 0.18,  # 18% for transportation
            "food": monthly_income * 0.15,  # 15% for food
            "utilities": monthly_income * 0.10,  # 10% for utilities
            "savings": monthly_income * 0.10,  # 10% for savings
            "healthcare": monthly_income * 0.05,  # 5% for healthcare
            "entertainment": monthly_income * 0.03,  # 3% for entertainment
            "miscellaneous": monthly_income * 0.04  # 4% for miscellaneous
        }
    elif monthly_income >= 8000:  # High income - more aggressive savings
        return {
            "housing": monthly_income * 0.25,  # 25% for housing
            "transportation": monthly_income * 0.12,  # 12% for transportation
            "food": monthly_income * 0.10,  # 10% for food
            "utilities": monthly_income * 0.06,  # 6% for utilities
            "savings": monthly_income * 0.30,  # 30% for savings
            "healthcare": monthly_income * 0.04,  # 4% for healthcare
            "entertainment": monthly_income * 0.08,  # 8% for entertainment
            "miscellaneous": monthly_income * 0.05  # 5% for miscellaneous
        }
    else:  # Medium income - balanced approach
        return {
            "housing": monthly_income * 0.30,  # 30% for housing
            "transportation": monthly_income * 0.15,  # 15% for transportation
            "food": monthly_income * 0.12,  # 12% for food
            "utilities": monthly_income * 0.08,  # 8% for utilities
            "savings": monthly_income * 0.20,  # 20% for savings
            "healthcare": monthly_income * 0.05,  # 5% for healthcare
            "entertainment": monthly_income * 0.05,  # 5% for entertainment
            "miscellaneous": monthly_income * 0.05  # 5% for miscellaneous
        }

def get_housing_recommendations(monthly_income, county):
    """Get housing recommendations based on income and county"""
    recommended_housing = monthly_income * 0.30
    
    # County-specific adjustments
    county_multipliers = {
        "San Francisco": 1.4,
        "Santa Clara": 1.3,
        "San Mateo": 1.35,
        "Alameda": 1.2,
        "Orange": 1.15,
        "Los Angeles": 1.1,
        "San Diego": 1.1,
        "Ventura": 1.05,
        "Contra Costa": 1.1,
        "Santa Barbara": 1.1
    }
    
    multiplier = county_multipliers.get(county, 1.0)
    adjusted_housing = recommended_housing * multiplier
    
    return {
        "recommended_max": min(adjusted_housing, monthly_income * 0.40),  # Cap at 40%
        "ideal_range": {
            "min": recommended_housing * 0.8,
            "max": recommended_housing * 1.2
        },
        "county_factor": multiplier,
        "tips": get_housing_tips(county, monthly_income)
    }

def get_housing_tips(county, monthly_income):
    """Get county-specific housing tips"""
    base_tips = [
        "Include utilities, parking, and renter's insurance in your housing budget",
        "Consider the total cost of commuting when choosing location",
        "Look for apartments with good public transit access to save on transportation"
    ]
    
    high_cost_counties = ["San Francisco", "Santa Clara", "San Mateo", "Alameda"]
    
    if county in high_cost_counties:
        base_tips.extend([
            "Consider house-hacking or finding roommates to reduce costs",
            "Look into suburbs with good transit connections to downtown",
            "Consider co-living spaces which can be more affordable"
        ])
    
    if monthly_income < 4000:
        base_tips.extend([
            "Look for rent-stabilized or affordable housing programs",
            "Consider shared housing options",
            "Prioritize neighborhoods with lower cost of living"
        ])
    
    return base_tips

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Hash password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        conn = sqlite3.connect('budget_app.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({"success": True, "message": "User registered successfully"})
    
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already exists"}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({"error": "Missing username or password"}), 400
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('budget_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username FROM users 
        WHERE username = ? AND password_hash = ?
    ''', (username, password_hash))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['username'] = user[1]
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"error": "Invalid username or password"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

@app.route('/api/calculate-budget', methods=['POST'])
def calculate_budget():
    data = request.get_json()
    yearly_income = float(data.get('yearly_income', 0))
    filing_status = data.get('filing_status', 'single')
    county = data.get('county', 'Los Angeles')
    
    if yearly_income <= 0:
        return jsonify({"error": "Invalid income amount"}), 400
    
    # Calculate taxes
    federal_tax = calculate_federal_tax(yearly_income, filing_status)
    state_tax = calculate_ca_state_tax(yearly_income, filing_status)
    county_tax = calculate_county_tax(yearly_income, county)
    
    # Social Security and Medicare (FICA)
    social_security_tax = min(yearly_income * 0.062, 160200 * 0.062)  # 6.2% up to wage base
    medicare_tax = yearly_income * 0.0145  # 1.45%
    
    # Additional Medicare tax for high earners
    if yearly_income > (200000 if filing_status == 'single' else 250000):
        additional_medicare = (yearly_income - (200000 if filing_status == 'single' else 250000)) * 0.009
        medicare_tax += additional_medicare
    
    total_taxes = federal_tax + state_tax + county_tax + social_security_tax + medicare_tax
    net_income = yearly_income - total_taxes
    monthly_net_income = net_income / 12
    
    # Determine income level for budget calculation
    income_level = 'low' if monthly_net_income < 3000 else 'high' if monthly_net_income >= 8000 else 'medium'
    
    # Calculate budget breakdown
    budget_breakdown = calculate_budget_breakdown(monthly_net_income, income_level)
    
    # Get housing recommendations
    housing_recommendations = get_housing_recommendations(monthly_net_income, county)
    
    # Save to database if user is logged in
    if 'user_id' in session:
        conn = sqlite3.connect('budget_app.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO budget_profiles (user_id, yearly_income, filing_status, county, housing_budget, transportation_budget, food_budget, savings_budget)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], yearly_income, filing_status, county, 
              budget_breakdown['housing'], budget_breakdown['transportation'], 
              budget_breakdown['food'], budget_breakdown['savings']))
        conn.commit()
        conn.close()
    
    return jsonify({
        "yearly_income": yearly_income,
        "federal_tax": round(federal_tax, 2),
        "state_tax": round(state_tax, 2),
        "county_tax": round(county_tax, 2),
        "social_security_tax": round(social_security_tax, 2),
        "medicare_tax": round(medicare_tax, 2),
        "total_taxes": round(total_taxes, 2),
        "net_yearly_income": round(net_income, 2),
        "monthly_net_income": round(monthly_net_income, 2),
        "budget_breakdown": {k: round(v, 2) for k, v in budget_breakdown.items()},
        "housing_recommendations": housing_recommendations,
        "tax_rate": round((total_taxes / yearly_income) * 100, 2),
        "income_level": income_level,
        "filing_status": filing_status,
        "county": county
    })

@app.route('/api/budget-tips', methods=['GET'])
def get_budget_tips():
    tips = {
        "housing": [
            "Keep housing costs at 30% or less of your monthly income in most CA counties",
            "In high-cost areas like SF and Silicon Valley, up to 35% may be necessary",
            "Include utilities, parking, and renter's insurance in your housing budget",
            "Research rent control laws in your city for tenant protections",
            "Consider house-hacking or roommates to reduce costs",
            "Look for apartments near public transit to save on transportation"
        ],
        "transportation": [
            "California has excellent public transportation in major cities",
            "Consider getting a monthly transit pass instead of driving daily",
            "If you must drive, budget for gas, insurance, maintenance, and parking",
            "Carpooling apps like Waze Carpool can reduce commute costs",
            "Electric vehicles may qualify for CA rebates and HOV lane access",
            "Bike-friendly cities like Davis and Berkeley can save money"
        ],
        "food": [
            "California has year-round farmers markets with affordable fresh produce",
            "Shop at stores like Trader Joe's, Costco, or ethnic grocery stores for savings",
            "Meal prep on weekends to avoid expensive takeout during busy weekdays",
            "Take advantage of happy hour specials and restaurant week deals",
            "Consider CSA (Community Supported Agriculture) boxes for fresh, local produce",
            "Generic brands can save 20-30% on grocery bills"
        ],
        "savings": [
            "Build an emergency fund with 3-6 months expenses (CA cost of living is high)",
            "Take advantage of employer 401(k) matching - it's free money",
            "California has high taxes, so consider Roth IRA for tax-free growth",
            "Look into high-yield savings accounts for emergency funds",
            "Automate savings transfers to make it effortless",
            "Consider investing in index funds for long-term growth"
        ],
        "utilities": [
            "California has tiered electricity rates - conserve during peak hours",
            "Solar panels may be cost-effective due to CA incentives and sunny weather",
            "Use programmable thermostats to save on heating/cooling costs",
            "Bundle internet, cable, and phone services for discounts",
            "Consider time-of-use electricity plans if you can shift usage",
            "Water conservation measures can significantly reduce bills"
        ],
        "healthcare": [
            "California has Covered California marketplace for health insurance",
            "Many employers offer HSA accounts - contribute pre-tax dollars",
            "Use urgent care instead of ER for non-emergency situations",
            "Look into community health centers for affordable care",
            "Consider telehealth options for routine consultations",
            "Preventive care is often covered 100% by insurance"
        ],
        "entertainment": [
            "Take advantage of California's free outdoor activities - beaches, hiking, parks",
            "Many museums have free days for residents",
            "Look for happy hour deals and early bird specials at restaurants",
            "Consider streaming services instead of cable TV",
            "Free events like outdoor concerts and festivals are common",
            "California libraries often have free events and classes"
        ],
        "general": [
            "California's cost of living varies dramatically by region - adjust expectations",
            "Track expenses for at least a month to understand spending patterns",
            "Use apps like Mint or YNAB to automate budget tracking",
            "Take advantage of California's strong consumer protection laws",
            "Consider side hustles - CA has a large gig economy",
            "Research local tax credits and deductions specific to California",
            "Plan for seasonal expenses like earthquake insurance or fire evacuation costs"
        ]
    }
    
    return jsonify(tips)

@app.route('/api/convert-income', methods=['POST'])
def convert_income():
    data = request.get_json()
    amount = float(data.get('amount', 0))
    from_type = data.get('from_type')  # 'hourly', 'monthly', 'yearly'
    hours_per_week = float(data.get('hours_per_week', 40))
    weeks_per_year = float(data.get('weeks_per_year', 52))
    
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400
    
    # Convert everything to yearly first
    if from_type == 'hourly':
        yearly = amount * hours_per_week * weeks_per_year
    elif from_type == 'monthly':
        yearly = amount * 12
    elif from_type == 'yearly':
        yearly = amount
    else:
        return jsonify({"error": "Invalid income type"}), 400
    
    # Calculate other formats
    monthly = yearly / 12
    hourly = yearly / (hours_per_week * weeks_per_year)
    weekly = yearly / weeks_per_year
    biweekly = yearly / 26  # 26 pay periods per year
    
    return jsonify({
        "yearly": round(yearly, 2),
        "monthly": round(monthly, 2),
        "hourly": round(hourly, 2),
        "weekly": round(weekly, 2),
        "biweekly": round(biweekly, 2)
    })

@app.route('/api/counties', methods=['GET'])
def get_counties():
    """Get list of California counties with tax rates"""
    counties = [
        {"name": county, "tax_rate": rate} 
        for county, rate in COUNTY_TAX_RATES.items()
    ]
    return jsonify(counties)

@app.route('/api/user-profile', methods=['GET'])
def get_user_profile():
    """Get user's budget history and profile"""
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    conn = sqlite3.connect('budget_app.db')
    cursor = conn.cursor()
    
    # Get recent budget profiles
    cursor.execute('''
        SELECT yearly_income, filing_status, county, housing_budget, transportation_budget, 
               food_budget, savings_budget, created_at
        FROM budget_profiles 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    ''', (session['user_id'],))
    
    profiles = cursor.fetchall()
    conn.close()
    
    profile_data = []
    for profile in profiles:
        profile_data.append({
            "yearly_income": profile[0],
            "filing_status": profile[1],
            "county": profile[2],
            "housing_budget": profile[3],
            "transportation_budget": profile[4],
            "food_budget": profile[5],
            "savings_budget": profile[6],
            "created_at": profile[7]
        })
    
    return jsonify({
        "username": session['username'],
        "profiles": profile_data
    })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Run the app
    app.run(debug=True, host='localhost', port=5000)