document.addEventListener("DOMContentLoaded", function() {
    const socket = io();
    const nameInput = document.getElementById('name-input');
    const submitNameBtn = document.getElementById('submit-name');
    const namesContainer = document.getElementById('names-container');
    const usernameInput = document.getElementById('username');
    const chatMessageInput = document.getElementById('chat-message');
    const sendMessageBtn = document.getElementById('send-message');
    const chatMessagesDiv = document.getElementById('chat-messages');
    const clearChatBtn = document.getElementById('clear-chat');
    
    let username = localStorage.getItem('username') || '';
    if (username) {
        usernameInput.value = username;
    }
    
    usernameInput.addEventListener('change', function() {
        username = usernameInput.value.trim();
        localStorage.setItem('username', username);
    });
    
    // Load existing suggestions
    fetch('/api/suggestions')
        .then(response => response.json())
        .then(suggestions => {
            suggestions.forEach(suggestion => {
                addSuggestionToDOM(suggestion);
            });
        });
    
    // Load existing chat messages
    fetch('/api/chat')
        .then(response => response.json())
        .then(messages => {
            messages.forEach(message => {
                addChatMessageToDOM(message);
            });
            // Scroll to bottom of chat
            chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
        });
    
    // Submit new name suggestion
    submitNameBtn.addEventListener('click', function() {
        submitNameSuggestion();
    });
    
    nameInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            submitNameSuggestion();
        }
    });
    
    // Clear Chat button event listener
    clearChatBtn.addEventListener('click', function() {
        if (confirm('Are you sure you want to clear all chat messages?')) {
            fetch('/api/chat/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
        }
    });
    
    function submitNameSuggestion() {
        const name = nameInput.value.trim();
        username = usernameInput.value.trim();
        
        if (!name) {
            alert('Please enter a name suggestion');
            return;
        }
        
        if (!username) {
            alert('Please enter your name');
            return;
        }
        
        fetch('/api/suggestions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                user: username
            })
        })
        .then(response => response.json())
        .then(suggestion => {
            nameInput.value = '';
        });
    }
    
    // Handle voting
    namesContainer.addEventListener('click', function(e) {
        if (!e.target.classList.contains('vote-btn')) return;
        
        username = usernameInput.value.trim();
        if (!username) {
            alert('Please enter your name');
            return;
        }
        
        const suggestionId = e.target.closest('.name-item').dataset.id;
        const voteType = e.target.dataset.vote;
        
        fetch(`/api/suggestions/${suggestionId}/vote`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                vote: voteType,
                user: username
            })
        });
    });
    
    // Handle edit and delete
    namesContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('edit-btn') || e.target.classList.contains('delete-btn')) {
            username = usernameInput.value.trim();
            if (!username) {
                alert('Please enter your name');
                return;
            }
            
            const nameItem = e.target.closest('.name-item');
            const suggestionId = nameItem.dataset.id;
            const suggestionUser = nameItem.dataset.user;
            
            if (username !== suggestionUser) {
                alert('You can only edit or delete your own suggestions');
                return;
            }
            
            if (e.target.classList.contains('edit-btn')) {
                const nameTitle = nameItem.querySelector('.name-title');
                const currentName = nameTitle.textContent;
                const newName = prompt('Edit your suggestion:', currentName);
                
                if (newName && newName !== currentName) {
                    fetch(`/api/suggestions/${suggestionId}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            name: newName,
                            user: username
                        })
                    });
                }
            } else if (e.target.classList.contains('delete-btn')) {
                if (confirm('Are you sure you want to delete this suggestion?')) {
                    fetch(`/api/suggestions/${suggestionId}`, {
                        method: 'DELETE',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            user: username
                        })
                    });
                }
            }
        }
    });
    
    // Send chat message
    sendMessageBtn.addEventListener('click', function() {
        sendChatMessage();
    });
    
    chatMessageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });
    
    function sendChatMessage() {
        const message = chatMessageInput.value.trim();
        username = usernameInput.value.trim();
        
        if (!message) return;
        
        if (!username) {
            alert('Please enter your name');
            return;
        }
        
        socket.emit('chat_message', {
            user: username,
            message: message
        });
        
        chatMessageInput.value = '';
    }
    
    // Socket.io event handlers
    socket.on("new_suggestion", function(suggestion) {
        addSuggestionToDOM(suggestion);
    });
    
    socket.on("vote_update", function(suggestion) {
        updateSuggestionInDOM(suggestion);
    });
    
    socket.on("suggestion_edited", function(suggestion) {
        updateSuggestionInDOM(suggestion);
    });
    
    socket.on("suggestion_deleted", function(data) {
        const nameItem = document.querySelector(`.name-item[data-id="${data.id}"]`);
        if (nameItem) {
            nameItem.remove();
        }
    });
    
    socket.on("new_chat_message", function(message) {
        addChatMessageToDOM(message);
        chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
    });
    
    // Add handler for chat cleared event
    socket.on("chat_cleared", function() {
        chatMessagesDiv.innerHTML = '';
    });
    
    function addSuggestionToDOM(suggestion) {
        const nameItem = document.createElement('div');
        nameItem.className = 'name-item';
        nameItem.dataset.id = suggestion.id;
        nameItem.dataset.user = suggestion.user;
        
        const nameHeader = document.createElement('div');
        nameHeader.className = 'name-header';
        
        const nameTitle = document.createElement('div');
        nameTitle.className = 'name-title';
        nameTitle.textContent = suggestion.name;
        
        const nameUser = document.createElement('div');
        nameUser.className = 'name-user';
        nameUser.textContent = `Suggested by: ${suggestion.user}`;
        
        nameHeader.appendChild(nameTitle);
        nameHeader.appendChild(nameUser);
        
        const voteButtons = document.createElement('div');
        voteButtons.className = 'vote-buttons';
        
        const upvoteBtn = document.createElement('button');
        upvoteBtn.className = 'btn vote-btn';
        upvoteBtn.dataset.vote = 'up';
        upvoteBtn.innerHTML = '<i class="fas fa-thumbs-up"></i> Upvote';
        
        const downvoteBtn = document.createElement('button');
        downvoteBtn.className = 'btn vote-btn';
        downvoteBtn.dataset.vote = 'down';
        downvoteBtn.innerHTML = '<i class="fas fa-thumbs-down"></i> Downvote';
        
        const voteCount = document.createElement('span');
        voteCount.className = 'vote-count';
        voteCount.textContent = `+${suggestion.upvotes} / -${suggestion.downvotes}`;
        
        voteButtons.appendChild(upvoteBtn);
        voteButtons.appendChild(voteCount);
        voteButtons.appendChild(downvoteBtn);
        
        const actionButtons = document.createElement('div');
        actionButtons.className = 'action-buttons';
        
        const editBtn = document.createElement('button');
        editBtn.className = 'btn edit-btn';
        editBtn.innerHTML = '<i class="fas fa-edit"></i> Edit';
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn delete-btn';
        deleteBtn.innerHTML = '<i class="fas fa-trash"></i> Delete';
        
        actionButtons.appendChild(editBtn);
        actionButtons.appendChild(deleteBtn);
        
        nameItem.appendChild(nameHeader);
        nameItem.appendChild(voteButtons);
        nameItem.appendChild(actionButtons);
        
        namesContainer.prepend(nameItem);
    }
    
    function updateSuggestionInDOM(suggestion) {
        const nameItem = document.querySelector(`.name-item[data-id="${suggestion.id}"]`);
        if (nameItem) {
            const nameTitle = nameItem.querySelector('.name-title');
            nameTitle.textContent = suggestion.name;
            
            const voteCount = nameItem.querySelector('.vote-count');
            voteCount.textContent = `+${suggestion.upvotes} / -${suggestion.downvotes}`;
        }
    }
    
    function addChatMessageToDOM(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        
        const userSpan = document.createElement('span');
        userSpan.className = 'user';
        userSpan.textContent = message.user + ': ';
        
        const messageText = document.createTextNode(message.message);
        
        messageDiv.appendChild(userSpan);
        messageDiv.appendChild(messageText);
        
        chatMessagesDiv.appendChild(messageDiv);
    }
});
