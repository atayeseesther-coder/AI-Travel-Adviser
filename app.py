import streamlit as st
import re
import json
import csv
import io
from datetime import datetime

EXCHANGE_RATES = {
    "NGN": 1.0, "USD": 1367.0, "GBP": 1720.0, "EUR": 1480.0,
    "GHS": 105.0, "KES": 10.5, "AED": 372.0,
}

CITY_COSTS = {
    "LAGOS": {"country": "Nigeria", "currency": "NGN", "hotel": 55000, "food": 18000, "transport": 12000, "flight": 0},
    "ABUJA": {"country": "Nigeria", "currency": "NGN", "hotel": 45000, "food": 15000, "transport": 10000, "flight": 120000},
    "ACCRA": {"country": "Ghana", "currency": "GHS", "hotel": 60000, "food": 20000, "transport": 12000, "flight": 350000},
    "NAIROBI": {"country": "Kenya", "currency": "KES", "hotel": 70000, "food": 22000, "transport": 15000, "flight": 550000},
    "DUBAI": {"country": "UAE", "currency": "AED", "hotel": 120000, "food": 35000, "transport": 25000, "flight": 900000},
    "LONDON": {"country": "UK", "currency": "GBP", "hotel": 150000, "food": 40000, "transport": 30000, "flight": 1200000},
}

PUBLIC_HOLIDAYS = {
    "2026-01-01": "New Year's Day",
    "2026-04-03": "Good Friday",
    "2026-04-06": "Easter Monday",
    "2026-05-01": "Workers' Day",
    "2026-06-12": "Democracy Day",
    "2026-10-01": "Independence Day",
    "2026-12-25": "Christmas Day",
    "2026-12-26": "Boxing Day",
}

class InvalidCurrencyError(Exception):
    pass
class InvalidInputError(Exception):
    pass
class ConversionError(Exception):
    pass

def validate_currency_code(code):
    if not re.match(r"^[A-Z]{3}$", code.strip().upper()):
        raise InvalidCurrencyError(f"Invalid code '{code}'. Use 3 letters e.g. NGN, USD, GBP")
    if code.strip().upper() not in EXCHANGE_RATES:
        raise InvalidCurrencyError(f"Currency '{code}' not supported")
    return code.strip().upper()

def extract_price(text):
    match = re.search(r"[\d,]+(?:\.\d+)?", str(text).replace(",", ""))
    if not match:
        raise InvalidInputError(f"Could not find price in '{text}'")
    return float(match.group().replace(",", ""))

class CurrencyConverter:
    def _init_(self, rates):
        self.rates = rates
    def convert(self, amount, from_currency, to_currency):
        try:
            from_cur = validate_currency_code(from_currency)
            to_cur = validate_currency_code(to_currency)
            amount_in_ngn = float(amount) * self.rates[from_cur]
            return round(amount_in_ngn / self.rates[to_cur], 2)
        except (ValueError, TypeError):
            raise ConversionError("Failed to convert - enter a valid number")

class Expense:
    def _init_(self, category, amount, note=""):
        self.category = category
        self.amount = float(amount)
        self.note = note
        self.date = datetime.now().strftime("%Y-%m-%d %H:%M")
    def to_dict(self):
        return {"category": self.category, "amount": self.amount, "note": self.note, "date": self.date}

class TripBudget:
    def _init_(self, home_currency, destination, total_budget, days, style="Comfort", group_size=1, travel_date=""):
        self.home_currency = validate_currency_code(home_currency)
        self.destination = destination.strip().upper()
        self.total_budget = float(total_budget)
        self.days = int(days)
        self.style = style
        self.group_size = int(group_size)
        self.travel_date = travel_date
        self.expenses = []
        if self.days <= 0:
            raise InvalidInputError("Days must be > 0")
        if self.total_budget <= 0:
            raise InvalidInputError("Budget must be > 0")
    def daily_limit(self):
        return round(self.total_budget / self.days, 2)
    def add_expense(self, expense):
        self.expenses.append(expense)
    def total_spent(self):
        return sum(e.amount for e in self.expenses)
    def remaining(self):
        return round(self.total_budget - self.total_spent(), 2)
    def check_holiday(self):
        if self.travel_date in PUBLIC_HOLIDAYS:
            return f"WARNING: {self.travel_date} is {PUBLIC_HOLIDAYS[self.travel_date]} - prices may be higher!"
        return "No public holiday on travel date."
    def estimate_cost(self):
        if self.destination not in CITY_COSTS:
            raise InvalidInputError(f"Destination '{self.destination}' not in database")
        city = CITY_COSTS[self.destination]
        multiplier = {"Budget": 0.7, "Comfort": 1.0, "Luxury": 1.8}.get(self.style, 1.0)
        hotel = city["hotel"] * multiplier * self.days
        food = city["food"] * multiplier * self.days * self.group_size
        transport = city["transport"] * multiplier * self.days
        flight = city["flight"]
        total = hotel + food + transport + flight
        return {"hotel": round(hotel, 2), "food": round(food, 2), "transport": round(transport, 2), "flight": round(flight, 2), "total": round(total, 2)}

class BudgetReport:
    def _init_(self, trip, converter):
        self.trip = trip
        self.converter = converter
    def ai_advice(self):
        est = self.trip.estimate_cost()
        budget = self.trip.total_budget
        total = est["total"]
        lines = []
        if total <= budget:
            lines.append(f"GOOD NEWS: Within budget! You have N{budget-total:,.0f} left.")
            lines.append("Tip: Keep 10% for emergency. You can upgrade hotel or add 1 activity day.")
        else:
            diff = total - budget
            lines.append(f"OVER BUDGET by N{diff:,.0f}. AI Suggestions:")
            lines.append(f"- Reduce days from {self.trip.days} to {max(1, self.trip.days-2)}")
            lines.append("- Switch Luxury -> Comfort or Comfort -> Budget")
            lines.append("- Try cheaper city: Dubai -> Accra, London -> Nairobi")
        return lines

def main():
    st.set_page_config(page_title="AI Travel Adviser", page_icon="✈️", layout="wide")
    st.title("✈️ AI Travel Adviser")
    st.write("Get personalised travel budget recommendations based on your destination, budget, currency and travel style.")
    st.divider()

    converter = CurrencyConverter(EXCHANGE_RATES)

    if "expenses" not in st.session_state:
        st.session_state.expenses = []

    st.subheader("Tell Us About Your Trip")
    col1, col2 = st.columns(2)
    with col1:
        home_currency = st.selectbox("Home Currency", list(EXCHANGE_RATES.keys()), index=0)
        destination = st.selectbox("Destination", list(CITY_COSTS.keys()), index=0)
        style = st.selectbox("Travel Style", ["Budget", "Comfort", "Luxury"], index=1)
    with col2:
        total_budget = st.number_input("Total Budget (in NGN)", min_value=1000.0, value=500000.0, step=10000.0)
        days = st.number_input("Number of Days", min_value=1, value=5, step=1)
        group_size = st.number_input("Group Size", min_value=1, value=1, step=1)
        travel_date = st.date_input("Travel Date").strftime("%Y-%m-%d")

    if st.button("Get My Travel Plan", type="primary"):
        try:
            trip = TripBudget(home_currency, destination, total_budget, days, style, group_size, travel_date)
            est = trip.estimate_cost()
            report = BudgetReport(trip, converter)

            st.subheader(f"📍 {destination} - {CITY_COSTS[destination]['country']} ({days} days, {style})")
            st.write(trip.check_holiday())
            st.write(f"*Daily Limit:* N{trip.daily_limit():,.2f}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Hotel", f"N{est['hotel']:,.0f}")
            c2.metric("Food", f"N{est['food']:,.0f}")
            c3.metric("Transport", f"N{est['transport']:,.0f}")
            c4.metric("Flight", f"N{est['flight']:,.0f}")
            c5.metric("Total Estimate", f"N{est['total']:,.0f}")

            st.subheader("🤖 AI Advice")
            for line in report.ai_advice():
                st.write(line)

            st.subheader("💱 Currency Converter")
            amt = st.number_input("Amount in NGN to convert", min_value=0.0, value=100000.0)
            to_cur = st.selectbox("Convert to", list(EXCHANGE_RATES.keys()), index=1)
            st.success(f"N{amt:,.0f} = {converter.convert(amt, 'NGN', to_cur):,.2f} {to_cur}")

        except Exception as e:
            st.error(f"Error: {e}")

if _name_ == "_main_":
    main()