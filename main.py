import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
import datetime

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'your_very_secret_key_please_change_it'
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False, nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'

class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    user_name = db.Column(db.String(80), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    votes = db.relationship('Vote', backref='suggestion', lazy=True, cascade="all, delete-orphan")

    def as_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'user_name': self.user_name,
            'timestamp': self.timestamp.isoformat(),
            'upvotes': sum(1 for vote in self.votes if vote.vote_type == 'upvote'),
            'downvotes': sum(1 for vote in self.votes if vote.vote_type == 'downvote'),
            'voters': [{'user_name': vote.user_name, 'vote_type': vote.vote_type} for vote in self.votes]
        }

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    suggestion_id = db.Column(db.Integer, db.ForeignKey('suggestion.id'), nullable=False)
    user_name = db.Column(db.String(80), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # 'upvote' or 'downvote'
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('suggestion_id', 'user_name', name='_suggestion_user_uc'),)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def as_dict(self):
        return {
            'id': self.id,
            'user_name': self.user_name,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }

with app.app_context():
    db.create_all()

# --- API Routes for Suggestions and Voting ---
@app.route('/api/suggestions', methods=['POST'])
def add_suggestion():
    data = request.get_json()
    user_name = data.get('user_name')
    text = data.get('text')
    if not user_name or not text:
        return jsonify({'error': 'User name and suggestion text are required'}), 400
    
    # Optional: Check if user exists or create one
    user = User.query.filter_by(name=user_name).first()
    if not user:
        user = User(name=user_name)
        db.session.add(user)
        # db.session.commit() # Commit if you want to save user immediately, or let it commit with suggestion

    new_suggestion = Suggestion(text=text, user_name=user_name)
    db.session.add(new_suggestion)
    db.session.commit()
    socketio.emit('new_suggestion', new_suggestion.as_dict(), room='product_namer_room')
    return jsonify(new_suggestion.as_dict()), 201

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    suggestions = Suggestion.query.order_by(Suggestion.timestamp.desc()).all()
    return jsonify([s.as_dict() for s in suggestions])

@app.route('/api/suggestions/<int:suggestion_id>', methods=['PUT'])
def update_suggestion(suggestion_id):
    data = request.get_json()
    user_name = data.get('user_name')
    new_text = data.get('text')

    if not user_name or not new_text:
        return jsonify({'error': 'User name and suggestion text are required'}), 400

    suggestion = Suggestion.query.get(suggestion_id)
    if not suggestion:
        return jsonify({'error': 'Suggestion not found'}), 404

    # Only allow the original suggester to edit
    if suggestion.user_name != user_name:
        return jsonify({'error': 'Only the original suggester can edit this suggestion'}), 403

    suggestion.text = new_text
    suggestion.timestamp = datetime.datetime.utcnow()  # Update timestamp to show it was edited
    db.session.commit()
    
    socketio.emit('suggestion_updated', suggestion.as_dict(), room='product_namer_room')
    return jsonify(suggestion.as_dict()), 200

@app.route('/api/suggestions/<int:suggestion_id>', methods=['DELETE'])
def delete_suggestion(suggestion_id):
    data = request.get_json()
    user_name = data.get('user_name')

    if not user_name:
        return jsonify({'error': 'User name is required'}), 400

    suggestion = Suggestion.query.get(suggestion_id)
    if not suggestion:
        return jsonify({'error': 'Suggestion not found'}), 404

    # Only allow the original suggester to delete
    if suggestion.user_name != user_name:
        return jsonify({'error': 'Only the original suggester can delete this suggestion'}), 403

    db.session.delete(suggestion)
    db.session.commit()
    
    socketio.emit('suggestion_deleted', {'id': suggestion_id}, room='product_namer_room')
    return jsonify({'success': True, 'message': 'Suggestion deleted'}), 200

@app.route('/api/suggestions/<int:suggestion_id>/vote', methods=['POST'])
def cast_vote(suggestion_id):
    data = request.get_json()
    user_name = data.get('user_name')
    vote_type = data.get('vote_type') # 'upvote' or 'downvote'

    if not user_name or not vote_type or vote_type not in ['upvote', 'downvote']:
        return jsonify({'error': 'User name and valid vote type (upvote/downvote) are required'}), 400

    suggestion = Suggestion.query.get(suggestion_id)
    if not suggestion:
        return jsonify({'error': 'Suggestion not found'}), 404

    # Optional: Check if user exists or create one
    user = User.query.filter_by(name=user_name).first()
    if not user:
        user = User(name=user_name)
        db.session.add(user)
        # db.session.commit() # Commit if you want to save user immediately

    existing_vote = Vote.query.filter_by(suggestion_id=suggestion_id, user_name=user_name).first()

    if existing_vote:
        if existing_vote.vote_type == vote_type:
            # User is clicking the same vote type again, remove the vote (toggle off)
            db.session.delete(existing_vote)
        else:
            # User is changing their vote type
            existing_vote.vote_type = vote_type
            existing_vote.timestamp = datetime.datetime.utcnow()
    else:
        # New vote
        new_vote = Vote(suggestion_id=suggestion_id, user_name=user_name, vote_type=vote_type)
        db.session.add(new_vote)
    
    db.session.commit()
    updated_suggestion = Suggestion.query.get(suggestion_id) # Fetch again to get updated vote counts
    socketio.emit('vote_update', updated_suggestion.as_dict(), room='product_namer_room')
    return jsonify(updated_suggestion.as_dict()), 200

# --- SocketIO Chat Events ---
@socketio.on('join')
def on_join(data):
    username = data.get('username', 'Anonymous') # Get username from client, default to 'Anonymous'
    room = 'product_namer_room' # Single room for everyone
    join_room(room)
    # Emit welcome message or user joined notification to the room
    emit('chat_message', {'user_name': 'System', 'message': f'{username} has joined the discussion.'}, room=room)
    # Send recent chat history to the newly joined user
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.asc()).limit(50).all()
    emit('chat_history', [msg.as_dict() for msg in messages]) # Send to the specific user who just joined

@socketio.on('send_message')
def handle_send_message(data):
    user_name = data.get('user_name')
    message_text = data.get('message')
    room = 'product_namer_room'

    if not user_name or not message_text:
        return # Or emit an error back to sender

    chat_msg = ChatMessage(user_name=user_name, message=message_text)
    db.session.add(chat_msg)
    db.session.commit()
    emit('chat_message', chat_msg.as_dict(), room=room)

@socketio.on('disconnect')
def on_disconnect():
    # For simplicity, we are not tracking specific users disconnecting from the room by name here
    # but you could implement user tracking if needed.
    # print('Client disconnected')
    pass # No specific action needed for this simple app

# --- Serve Static Files (React build or simple HTML) ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            # Fallback for initial setup if index.html doesn't exist yet
            return "Welcome to Product Namer! Frontend not yet built.", 200

if __name__ == '__main__':
    # Use eventlet or gevent for production with SocketIO
    # For development, Flask's built-in server is fine with allow_unsafe_werkzeug=True
    # For a more robust setup, you'd use a proper WSGI server like Gunicorn with eventlet or gevent workers.
    # Example: gunicorn --worker-class eventlet -w 1 module:app
    print("Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug for dev with Flask reloader

