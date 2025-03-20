document.getElementById('chatForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const userInput = document.getElementById('userInput').value;
    if (userInput) {
        showLoading();
        displayUserMessage(userInput);
        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: this.querySelector('[name=user_id]').value,
                age: this.querySelector('[name=age]') ? this.querySelector('[name=age]').value : null,
                sex: this.querySelector('[name=sex]') ? this.querySelector('[name=sex]').value : null,
                input: userInput
            })
        }).then(response => response.json()).then(data => {
            hideLoading();
            updateChat(data);
            document.getElementById('userInput').value = ''; // Clear input
        }).catch(error => {
            hideLoading();
            console.error('Error submitting initial input:', error);
            updateChat({ error_message: "Failed to send message. Please try again." });
        });
    }
});

// Event delegation for all submit buttons within follow-up divs
document.addEventListener('click', function(e) {
    if (e.target && e.target.tagName === 'BUTTON' && e.target.classList.contains('follow-up-submit')) {
        const followUpDiv = e.target.closest('.follow-up');
        console.log('Submit clicked in follow-up div:', followUpDiv); // Debug log
        submitAnswer(followUpDiv);
    }
});

function submitAnswer(followUpDiv) {
    if (!followUpDiv) {
        console.error('No follow-up div found for submission');
        return;
    }

    let selectedValues = [];
    const questionData = followUpDiv.dataset; // Access data attributes if set in the future

    // Determine the input type based on the follow-up div's content
    const selectElement = followUpDiv.querySelector('.answer-select');
    const checkboxes = followUpDiv.querySelectorAll('input[type="checkbox"]');
    const freeTextInput = followUpDiv.querySelector('input[name="free_text"]');

    if (selectElement && !selectElement.multiple) {
        // Handle single-select dropdown
        const selectedValue = selectElement.value;
        if (selectedValue) {
            selectedValues = [selectedValue];
        } else {
            console.log('No option selected in dropdown:', selectElement);
            return;
        }
    } else if (checkboxes.length > 0) {
        // Handle checkboxes (group_multiple)
        selectedValues = Array.from(checkboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        if (selectedValues.length === 0) {
            console.log('No checkboxes selected in:', followUpDiv);
            return;
        }
    } else if (freeTextInput) {
        // Handle free text
        const textValue = freeTextInput.value.trim();
        if (textValue) {
            selectedValues = [textValue];
        } else {
            console.log('No text entered in:', freeTextInput);
            return;
        }
    } else {
        console.error('No valid input found in follow-up div:', followUpDiv);
        return;
    }

    console.log('Submitting values:', selectedValues); // Debug log
    if (selectedValues.length > 0) {
        showLoading();
        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: document.querySelector('[name=user_id]').value,
                answer: selectedValues
            })
        }).then(response => {
            if (!response.ok) throw new Error('Network response was not ok: ' + response.statusText);
            return response.json();
        }).then(data => {
            hideLoading();
            updateChat(data);
            if (selectElement) selectElement.value = ''; // Reset dropdown
            if (freeTextInput) freeTextInput.value = ''; // Reset text input
        }).catch(error => {
            hideLoading();
            console.error('Error submitting answer:', error);
            updateChat({ error_message: "Failed to submit answer. Please try again." });
        });
    }
}

function submitFreeText() {
    const input = document.querySelector('[name=free_text]');
    if (input && input.value) {
        showLoading();
        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: document.querySelector('[name=user_id]').value,
                free_text: input.value
            })
        }).then(response => response.json()).then(data => {
            hideLoading();
            updateChat(data);
            input.value = '';
        }).catch(error => {
            hideLoading();
            console.error('Error submitting free text:', error);
            updateChat({ error_message: "Failed to submit free text. Please try again." });
        });
    }
}

function resetSession() {
    showLoading();
    fetch('/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: document.querySelector('[name=user_id]').value })
    }).then(response => response.json()).then(data => {
        hideLoading();
        document.getElementById('chatMessages').innerHTML = ''; // Clear chat
        updateChat(data);
    }).catch(error => {
        hideLoading();
        console.error('Error resetting session:', error);
        updateChat({ error_message: "Failed to reset session. Please try again." });
    });
}

function dismissFitbitAlert() {
    const alert = document.getElementById('fitbitAlert');
    if (alert) {
        alert.style.display = 'none';
    }
}

function showLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.style.display = 'block';
    }
}

function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.style.display = 'none';
    }
}

function displayUserMessage(text) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = text + '<span class="timestamp">' + new Date().toLocaleTimeString() + '</span>';
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function updateChat(data) {
    const chatMessages = document.getElementById('chatMessages');
    if (data.message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        messageDiv.innerHTML = data.message.replace('**Note:** Fitbit Charge 5 data is unavailable. Please open the Fitbit app and sync your device.', '').trim() + 
                              '<span class="timestamp">' + new Date().toLocaleTimeString() + '</span>';
        chatMessages.appendChild(messageDiv);
    }
    if (data.follow_up && data.follow_up !== "This is my final assessment based on your symptoms.") {
        const followUpDiv = document.createElement('div');
        followUpDiv.className = 'follow-up';
        followUpDiv.innerHTML = '<p>' + data.follow_up.text + '</p>';
        if (data.follow_up.ui_hint === 'dropdown') {
            // For group_single, ensure single selection
            followUpDiv.innerHTML += '<select class="answer-select"><option value="" disabled selected>Select an option</option>' + 
                data.follow_up.options.map(opt => `<option value="${opt}">${opt}</option>`).join('') + '</select>';
            followUpDiv.innerHTML += '<button type="button" class="follow-up-submit">Submit</button>';
        } else if (data.follow_up.ui_hint === 'checkboxes') {
            followUpDiv.innerHTML += data.follow_up.options.map(opt => `<label><input type="checkbox" name="answer" value="${opt}"> ${opt}</label>`).join('') + 
                '<button type="button" class="follow-up-submit">Submit</button>';
        } else if (data.follow_up.ui_hint === 'text') {
            followUpDiv.innerHTML += '<input type="text" name="free_text" placeholder="Describe your answer (e.g., \'2 days\')..." onkeypress="if(event.key === \'Enter\') submitFreeText()">' +
                '<button type="button" class="follow-up-submit">Submit</button>';
        }
        chatMessages.appendChild(followUpDiv);
    } else if (data.follow_up === "This is my final assessment based on your symptoms.") {
        const followUpDiv = document.createElement('div');
        followUpDiv.className = 'follow-up final';
        followUpDiv.innerHTML = '<p>' + data.follow_up + '</p>';
        chatMessages.appendChild(followUpDiv);
    }
    if (data.smartwatch_data) {
        const fitbitDiv = document.createElement('div');
        fitbitDiv.className = 'message bot-message';
        fitbitDiv.innerHTML = `SpO2: <span class="fitbit-value">${data.smartwatch_data.sp02 || 'N/A'}</span>%, Heart Rate: <span class="fitbit-value">${data.smartwatch_data.heart_rate || 'N/A'}</span> bpm` +
            '<span class="timestamp">' + new Date().toLocaleTimeString() + '</span>';
        chatMessages.appendChild(fitbitDiv);
    }
    if (data.error_message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = data.error_message + '<span class="timestamp">' + new Date().toLocaleTimeString() + '</span>';
        chatMessages.appendChild(errorDiv);
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function checkAge() {
    const age = parseInt(document.getElementById('ageSelect').value);
    const ageError = document.getElementById('ageError');
    if (age < 18) {
        ageError.style.display = 'block';
    } else {
        ageError.style.display = 'none';
    }
}

function validateAge() {
    const age = parseInt(document.getElementById('ageSelect')?.value);
    if (age < 18) {
        return false;
    }
    return true;
}