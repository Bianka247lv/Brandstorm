from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import os
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'brandstorm_secret_key'
socketio = SocketIO(app)

# Initialize database
def init_db():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS suggestions
                 (id INTEGER PRIMARY KEY, name TEXT, user TEXT, upvotes INTEGER, downvotes INTEGER, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS votes
                 (id INTEGER PRIMARY KEY, suggestion_id INTEGER, user TEXT, vote TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages
                 (id INTEGER PRIMARY KEY, user TEXT, message TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM suggestions ORDER BY timestamp DESC")
    suggestions = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(suggestions)

@app.route('/api/suggestions', methods=['POST'])
def add_suggestion():
    data = request.json
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("INSERT INTO suggestions (name, user, upvotes, downvotes, timestamp) VALUES (?, ?, ?, ?, ?)",
              (data['name'], data['user'], 0, 0, datetime.now().isoformat()))
    suggestion_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Get the newly created suggestion
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,))
    suggestion = dict(c.fetchone())
    conn.close()
    
    socketio.emit('new_suggestion', suggestion)
    return jsonify(suggestion)

@app.route('/api/suggestions/<int:suggestion_id>/vote', methods=['POST'])
def vote_suggestion(suggestion_id):
    data = request.json
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    
    # Check if user has already voted
    c.execute("SELECT vote FROM votes WHERE suggestion_id = ? AND user = ?", (suggestion_id, data['user']))
    existing_vote = c.fetchone()
    
    if existing_vote:
        # User has already voted, update their vote
        old_vote = existing_vote[0]
        if old_vote != data['vote']:
            # Change vote
            c.execute("UPDATE votes SET vote = ? WHERE suggestion_id = ? AND user = ?", 
                     (data['vote'], suggestion_id, data['user']))
            
            # Update suggestion vote counts
            if old_vote == 'up':
                c.execute("UPDATE suggestions SET upvotes = upvotes - 1 WHERE id = ?", (suggestion_id,))
            else:
                c.execute("UPDATE suggestions SET downvotes = downvotes - 1 WHERE id = ?", (suggestion_id,))
                
            if data['vote'] == 'up':
                c.execute("UPDATE suggestions SET upvotes = upvotes + 1 WHERE id = ?", (suggestion_id,))
            else:
                c.execute("UPDATE suggestions SET downvotes = downvotes + 1 WHERE id = ?", (suggestion_id,))
    else:
        # New vote
        c.execute("INSERT INTO votes (suggestion_id, user, vote) VALUES (?, ?, ?)", 
                 (suggestion_id, data['user'], data['vote']))
        
        # Update suggestion vote count
        if data['vote'] == 'up':
            c.execute("UPDATE suggestions SET upvotes = upvotes + 1 WHERE id = ?", (suggestion_id,))
        else:
            c.execute("UPDATE suggestions SET downvotes = downvotes + 1 WHERE id = ?", (suggestion_id,))
    
    conn.commit()
    
    # Get updated suggestion
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,))
    suggestion = dict(c.fetchone())
    conn.close()
    
    socketio.emit('vote_update', suggestion)
    return jsonify(suggestion)

@app.route('/api/suggestions/<int:suggestion_id>', methods=['PUT'])
def edit_suggestion(suggestion_id):
    data = request.json
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("UPDATE suggestions SET name = ? WHERE id = ? AND user = ?", 
             (data['name'], suggestion_id, data['user']))
    conn.commit()
    
    # Get updated suggestion
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,))
    suggestion = dict(c.fetchone())
    conn.close()
    
    socketio.emit('suggestion_edited', suggestion)
    return jsonify(suggestion)

@app.route('/api/suggestions/<int:suggestion_id>', methods=['DELETE'])
def delete_suggestion(suggestion_id):
    data = request.json
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("DELETE FROM suggestions WHERE id = ? AND user = ?", (suggestion_id, data['user']))
    c.execute("DELETE FROM votes WHERE suggestion_id = ?", (suggestion_id,))
    conn.commit()
    conn.close()
    
    socketio.emit('suggestion_deleted', {'id': suggestion_id})
    return jsonify({'success': True})

@app.route('/api/chat', methods=['GET'])
def get_chat_messages():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM chat_messages ORDER BY timestamp ASC")
    messages = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(messages)

@socketio.on('chat_message')
def handle_chat_message(data):
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO chat_messages (user, message, timestamp) VALUES (?, ?, ?)",
              (data['user'], data['message'], timestamp))
    message_id = c.lastrowid
    conn.commit()
    conn.close()
    
    message = {
        'id': message_id,
        'user': data['user'],
        'message': data['message'],
        'timestamp': timestamp
    }
    
    socketio.emit('new_chat_message', message)

@app.route('/templates/<path:path>')
def serve_template(path):
    return render_template(path)

@app.route('/static/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
    @app.route('/api/chat/clear', methods=['POST'])
def clear_chat_messages():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    
    socketio.emit('chat_cleared')
    return jsonify({'success': True})

