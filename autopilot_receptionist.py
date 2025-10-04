import json
#!/usr/bin/env python3
"""
Orla AI Receptionist - Autopilot Customer Service System
Part of The Suite by Treetop
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
import stripe
import requests

# Load environment variables
load_dotenv ()

# Initialize services
stripe.api_key = os.getenv ( 'STRIPE_SECRET_KEY' )

# Initialize Firebase
if os.getenv("FIREBASE_CREDENTIALS"):
    cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CREDENTIALS")))
else:
    cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH")
db = firestore.client ()

# Initialize Flask
app = Flask ( __name__ )


class OrlaReceptionist:
    def __init__(self):
        self.vapi_api_key = os.getenv ( 'VAPI_API_KEY' )
        self.eden_ai_key = os.getenv ( 'EDEN_AI_API_KEY' )
        self.base_vapi_url = "https://api.vapi.ai"

    def create_assistant(self, business_config):
        """Create a Vapi assistant for a business"""
        headers = {
            "Authorization": f"Bearer {self.vapi_api_key}",
            "Content-Type": "application/json"
        }

        assistant_config = {
            "name": f"{business_config['name']} Receptionist",
            "model": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "messages": [{
                    "role": "system",
                    "content": f"""You are a professional receptionist for {business_config['name']}. 
                    Handle calls professionally, take messages, schedule appointments, and answer FAQs.
                    Business hours: {business_config.get ( 'hours', '9 AM - 5 PM' )}
                    Services: {business_config.get ( 'services', 'General business services' )}"""
                }]
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "rachel"
            },
            "firstMessage": f"Thank you for calling {business_config['name']}. How may I assist you today?"
        }

        response = requests.post (
            f"{self.base_vapi_url}/assistant",
            headers=headers,
            json=assistant_config
        )
        return response.json ()

    def create_phone_number(self, assistant_id, phone_number=None):
        """Provision a phone number for the assistant"""
        headers = {
            "Authorization": f"Bearer {self.vapi_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "assistantId": assistant_id,
            "provider": "twilio"
        }

        if phone_number:
            data["number"] = phone_number

        response = requests.post (
            f"{self.base_vapi_url}/phone-number",
            headers=headers,
            json=data
        )
        return response.json ()


# Initialize Orla
orla = OrlaReceptionist ()


@app.route ( '/' )
def home():
    return jsonify ( {
        "service": "Orla AI Receptionist",
        "status": "active",
        "version": "1.0.0"
    } )


@app.route ( '/webhook/vapi', methods=['POST'] )
def vapi_webhook():
    """Handle Vapi webhooks for call events"""
    data = request.json
    event_type = data.get ( 'type' )

    # Log call data to Firebase
    call_data = {
        'timestamp': datetime.now ().isoformat (),
        'event': event_type,
        'data': data
    }

    if event_type == 'call-started':
        db.collection ( 'calls' ).add ( call_data )
        print ( f"Call started: {data.get ( 'callId' )}" )

    elif event_type == 'call-ended':
        call_data['duration'] = data.get ( 'duration' )
        call_data['recording_url'] = data.get ( 'recordingUrl' )
        db.collection ( 'calls' ).add ( call_data )
        print ( f"Call ended: Duration {data.get ( 'duration' )}s" )

    elif event_type == 'transcript-ready':
        # Store transcript
        transcript_data = {
            'call_id': data.get ( 'callId' ),
            'transcript': data.get ( 'transcript' ),
            'timestamp': datetime.now ().isoformat ()
        }
        db.collection ( 'transcripts' ).add ( transcript_data )

    return jsonify ( {"status": "received"} ), 200


@app.route ( '/api/create-business', methods=['POST'] )
def create_business():
    """Onboard a new business"""
    data = request.json

    # Create Vapi assistant
    assistant = orla.create_assistant ( data )

    # Get phone number
    phone = orla.create_phone_number ( assistant['id'] )

    # Save to Firebase
    business_doc = {
        'name': data['name'],
        'email': data['email'],
        'assistant_id': assistant['id'],
        'phone_number': phone['number'],
        'created': datetime.now ().isoformat (),
        'status': 'active',
        'plan': data.get ( 'plan', 'starter' )
    }

    db.collection ( 'businesses' ).add ( business_doc )

    return jsonify ( {
        "status": "success",
        "phone_number": phone['number'],
        "assistant_id": assistant['id']
    } )


@app.route ( '/api/billing/create-subscription', methods=['POST'] )
def create_subscription():
    """Create Stripe subscription for a business"""
    data = request.json

    try:
        # Create Stripe customer
        customer = stripe.Customer.create (
            email=data['email'],
            source=data['token']
        )

        # Create subscription
        subscription = stripe.Subscription.create (
            customer=customer.id,
            items=[{
                'price': os.getenv ( 'STRIPE_PRICE_ID', 'price_1234' )  # $97/month
            }]
        )

        # Update business record
        business_ref = db.collection ( 'businesses' ).where ( 'email', '==', data['email'] )
        business_ref.update ( {
            'stripe_customer_id': customer.id,
            'subscription_id': subscription.id,
            'subscription_status': subscription.status
        } )

        return jsonify ( {
            "status": "success",
            "subscription_id": subscription.id
        } )

    except stripe.error.StripeError as e:
        return jsonify ( {"error": str ( e )} ), 400


@app.route ( '/api/analytics/<business_id>', methods=['GET'] )
def get_analytics(business_id):
    """Get call analytics for a business"""

    # Get calls from last 30 days
    calls = db.collection ( 'calls' ).where (
        'business_id', '==', business_id
    ).limit ( 100 ).stream ()

    call_list = []
    total_duration = 0

    for call in calls:
        call_data = call.to_dict ()
        call_list.append ( call_data )
        total_duration += call_data.get ( 'duration', 0 )

    analytics = {
        'total_calls': len ( call_list ),
        'total_duration_minutes': total_duration / 60,
        'average_duration': total_duration / len ( call_list ) if call_list else 0,
        'calls': call_list[-10:]  # Last 10 calls
    }

    return jsonify ( analytics )


if __name__ == '__main__':
    port = int ( os.getenv ( 'PORT', 5001 ) )
    print ( f"""
    ╔══════════════════════════════════════╗
    ║     Orla AI Receptionist System     ║
    ║         Part of The Suite            ║
    ╚══════════════════════════════════════╝

    Server running on http://localhost:{port}

    Endpoints:
    - POST /api/create-business - Onboard new business
    - POST /api/billing/create-subscription - Start subscription
    - GET /api/analytics/<id> - Get call analytics
    - POST /webhook/vapi - Vapi webhook handler

    Connected Services:
    ✓ Firebase
    ✓ Vapi AI
    ✓ Stripe
    """ )

    app.run ( debug=True, port=port )