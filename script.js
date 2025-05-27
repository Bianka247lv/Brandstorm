document.addEventListener("DOMContentLoaded", () => {
    const socket = io(); // Connect to Socket.IO server, assumes same host and port

    // User Name Elements
    const userNameInput = document.getElementById("userName");
    const setUserNameBtn = document.getElementById("setUserNameBtn");

    // Suggestion Elements
    const suggestionTextInput = document.getElementById("suggestionText");
    const submitSuggestionBtn = document.getElementById("submitSuggestionBtn");
    const nameListDiv = document.getElementById("nameList");

    // Chat Elements
    const chatWindowDiv = document.getElementById("chatWindow");
    const chatMessageInput = document.getElementById("chatMessageInput");
    const sendChatMessageBtn = document.getElementById("sendChatMessageBtn");

    let currentUserName = localStorage.getItem("productNamerUserName") || "";
    if (currentUserName) {
        userNameInput.value = currentUserName;
        userNameInput.disabled = true;
        setUserNameBtn.textContent = "Change Name";
        setUserNameBtn.disabled = true; // Or allow changing name
        joinChat(currentUserName);
    }

    // --- User Name Handling ---
    setUserNameBtn.addEventListener("click", () => {
        const name = userNameInput.value.trim();
        if (name) {
            currentUserName = name;
            localStorage.setItem("productNamerUserName", currentUserName);
            userNameInput.disabled = true;
            setUserNameBtn.textContent = "Name Set";
            setUserNameBtn.disabled = true;
            joinChat(currentUserName);
            alert(`Name set to: ${currentUserName}`);
        } else {
            alert("Please enter a name.");
        }
    });

    function checkUserName() {
        if (!currentUserName) {
            alert("Please set your name first!");
            userNameInput.focus();
            return false;
        }
        return true;
    }

    // --- Suggestion Handling ---
    async function fetchSuggestions() {
        try {
            const response = await fetch("/api/suggestions");
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const suggestions = await response.json();
            renderSuggestions(suggestions);
        } catch (error) {
            console.error("Error fetching suggestions:", error);
            nameListDiv.innerHTML = "<p>Error loading suggestions.</p>";
        }
    }

    function renderSuggestions(suggestions) {
        nameListDiv.innerHTML = ""; // Clear existing list
        if (suggestions.length === 0) {
            nameListDiv.innerHTML = "<p>No suggestions yet. Be the first!</p>";
            return;
        }
        suggestions.sort((a, b) => (b.upvotes - b.downvotes) - (a.upvotes - a.downvotes) || new Date(b.timestamp) - new Date(a.timestamp)); // Sort by net votes, then by time

        suggestions.forEach(suggestion => {
            const item = document.createElement("div");
            item.classList.add("suggestion-item");
            item.dataset.id = suggestion.id;

            let votersHTML = "";
            if(suggestion.voters && suggestion.voters.length > 0) {
                const upvoters = suggestion.voters.filter(v => v.vote_type === 'upvote').map(v => v.user_name).join(', ');
                const downvoters = suggestion.voters.filter(v => v.vote_type === 'downvote').map(v => v.user_name).join(', ');
                if (upvoters) votersHTML += `<br>Upvoted by: ${upvoters}`;
                if (downvoters) votersHTML += `<br>Downvoted by: ${downvoters}`;
            }

            // Check if current user is the suggester to show edit/delete buttons
            const isOwner = currentUserName === suggestion.user_name;
            const actionButtons = isOwner ? `
                <div class="action-buttons">
                    <button class="edit-btn"><i class="fas fa-edit"></i> Edit</button>
                    <button class="delete-btn"><i class="fas fa-trash"></i> Delete</button>
                </div>
                <div class="edit-form">
                    <input type="text" class="edit-input" value="${suggestion.text}">
                    <button class="save-edit-btn">Save</button>
                    <button class="cancel-edit-btn">Cancel</button>
                </div>
            ` : '';

            item.innerHTML = `
                <h3>${suggestion.text}</h3>
                <p class="suggester">Suggested by: ${suggestion.user_name} on ${new Date(suggestion.timestamp).toLocaleString()}</p>
                <p class="votes">Upvotes: <span class="upvote-count">${suggestion.upvotes}</span> | Downvotes: <span class="downvote-count">${suggestion.downvotes}</span></p>
                <div class="vote-buttons">
                    <button class="upvote-btn"><i class="fas fa-thumbs-up"></i> Upvote</button>
                    <button class="downvote-btn"><i class="fas fa-thumbs-down"></i> Downvote</button>
                </div>
                ${actionButtons}
                <p class="voters-list">${votersHTML ? votersHTML.substring(4) : 'No votes yet.'}</p>
            `;
            nameListDiv.appendChild(item);
        });
    }

    submitSuggestionBtn.addEventListener("click", async () => {
        if (!checkUserName()) return;
        const text = suggestionTextInput.value.trim();
        if (text) {
            try {
                const response = await fetch("/api/suggestions", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ text: text, user_name: currentUserName }),
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
                // const newSuggestion = await response.json(); // SocketIO will handle update
                suggestionTextInput.value = ""; // Clear input
                // fetchSuggestions(); // Re-fetch or wait for SocketIO update
            } catch (error) {
                console.error("Error submitting suggestion:", error);
                alert("Failed to submit suggestion: " + error.message);
            }
        } else {
            alert("Please enter a suggestion.");
        }
    });

    nameListDiv.addEventListener("click", async (event) => {
        if (!checkUserName()) return;
        const target = event.target.closest("button") || event.target; // Handle clicks on icons inside buttons
        const suggestionItem = target.closest(".suggestion-item");
        if (!suggestionItem) return;

        const suggestionId = suggestionItem.dataset.id;
        
        // Handle voting
        if (target.classList.contains("upvote-btn")) {
            try {
                const response = await fetch(`/api/suggestions/${suggestionId}/vote`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ user_name: currentUserName, vote_type: "upvote" }),
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
            } catch (error) {
                console.error("Error casting vote:", error);
                alert("Failed to cast vote: " + error.message);
            }
        } 
        else if (target.classList.contains("downvote-btn")) {
            try {
                const response = await fetch(`/api/suggestions/${suggestionId}/vote`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ user_name: currentUserName, vote_type: "downvote" }),
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
            } catch (error) {
                console.error("Error casting vote:", error);
                alert("Failed to cast vote: " + error.message);
            }
        }
        // Handle edit button
        else if (target.classList.contains("edit-btn")) {
            const editForm = suggestionItem.querySelector(".edit-form");
            editForm.style.display = "block";
        }
        // Handle cancel edit button
        else if (target.classList.contains("cancel-edit-btn")) {
            const editForm = suggestionItem.querySelector(".edit-form");
            editForm.style.display = "none";
        }
        // Handle save edit button
        else if (target.classList.contains("save-edit-btn")) {
            const editInput = suggestionItem.querySelector(".edit-input");
            const newText = editInput.value.trim();
            
            if (newText) {
                try {
                    const response = await fetch(`/api/suggestions/${suggestionId}`, {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ user_name: currentUserName, text: newText }),
                    });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                    }
                    
                    const editForm = suggestionItem.querySelector(".edit-form");
                    editForm.style.display = "none";
                    // SocketIO will handle update
                } catch (error) {
                    console.error("Error updating suggestion:", error);
                    alert("Failed to update suggestion: " + error.message);
                }
            } else {
                alert("Please enter a suggestion text.");
            }
        }
        // Handle delete button
        else if (target.classList.contains("delete-btn")) {
            if (confirm("Are you sure you want to delete this suggestion?")) {
                try {
                    const response = await fetch(`/api/suggestions/${suggestionId}`, {
                        method: "DELETE",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ user_name: currentUserName }),
                    });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                    }
                    // SocketIO will handle update
                } catch (error) {
                    console.error("Error deleting suggestion:", error);
                    alert("Failed to delete suggestion: " + error.message);
                }
            }
        }
    });

    // --- Chat Handling ---
    function joinChat(username) {
        if (username) {
            socket.emit("join", { username: username });
        }
    }

    sendChatMessageBtn.addEventListener("click", () => {
        if (!checkUserName()) return;
        const message = chatMessageInput.value.trim();
        if (message) {
            socket.emit("send_message", { user_name: currentUserName, message: message });
            chatMessageInput.value = ""; // Clear input
        }
    });
    
    chatMessageInput.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            event.preventDefault(); // Prevent default form submission if it were in a form
            sendChatMessageBtn.click();
        }
    });

    function displayChatMessage(data, isHistory = false) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("chat-message");
        if (data.user_name === "System") {
            messageElement.classList.add("system");
            messageElement.textContent = data.message;
        } else {
            messageElement.innerHTML = `<span class="user">${data.user_name}:</span> <span class="text">${data.message}</span> <span class="timestamp" style="font-size:0.7em; color:#999; float:right;">${new Date(data.timestamp).toLocaleTimeString()}</span>`;
        }
        chatWindowDiv.appendChild(messageElement);
        if (!isHistory) { // Scroll to bottom only for new messages
            chatWindowDiv.scrollTop = chatWindowDiv.scrollHeight;
        }
    }

    // --- Socket.IO Event Listeners ---
    socket.on("connect", () => {
        console.log("Connected to Socket.IO server!");
        if (currentUserName) {
            joinChat(currentUserName); // Re-join if connection was lost and re-established
        }
    });

    socket.on("new_suggestion", (suggestion) => {
        console.log("New suggestion received:", suggestion);
        fetchSuggestions(); // Re-fetch all to ensure correct order and full data
    });

    socket.on("vote_update", (updatedSuggestion) => {
        console.log("Vote update received:", updatedSuggestion);
        fetchSuggestions(); // Re-fetch all to ensure correct order and full data
    });
    
    socket.on("suggestion_updated", (updatedSuggestion) => {
        console.log("Suggestion updated:", updatedSuggestion);
        fetchSuggestions(); // Re-fetch all to ensure correct order and full data
    });
    
    socket.on("suggestion_deleted", (data) => {
        console.log("Suggestion deleted:", data);
        fetchSuggestions(); // Re-fetch all to ensure correct order and full data
    });

    socket.on("chat_message", (data) => {
        console.log("Chat message received:", data);
        displayChatMessage(data);
    });

    socket.on("chat_history", (messages) => {
        console.log("Chat history received:", messages);
        chatWindowDiv.innerHTML = ""; // Clear previous messages if any
        messages.forEach(msg => {
            displayChatMessage(msg, true);
        });
        chatWindowDiv.scrollTop = chatWindowDiv.scrollHeight; // Scroll to bottom after loading history
    });

    socket.on("disconnect", () => {
        console.log("Disconnected from Socket.IO server.");
    });

    // Initial load
    fetchSuggestions();
});
