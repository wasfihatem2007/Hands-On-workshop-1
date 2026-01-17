let currentPatientId = null;
let currentFontSize = 16;

function selectPatient(id, name) {
    currentPatientId = id;
    document.getElementById('current-patient-name').innerText = "Chatting with: " + name;
    
    document.querySelectorAll('.patient-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + id).classList.add('active');
    
    document.getElementById('user-input').disabled = false;
    document.getElementById('send-btn').disabled = false;
    document.getElementById('reset-btn').disabled = false;
    
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML = '<div class="msg ai">Hello. (Patient is waiting for you)</div>';
    
    chatBox.style.fontSize = currentFontSize + 'px';
}

function changeFontSize(amount) {
    currentFontSize += amount;
    
    if (currentFontSize < 12) currentFontSize = 12;
    if (currentFontSize > 24) currentFontSize = 24;

    const chatBox = document.getElementById('chat-box');
    chatBox.style.fontSize = currentFontSize + 'px';
    
    const display = document.getElementById('font-display');
    if (currentFontSize === 16) {
        display.innerText = "Normal";
    } else if (currentFontSize > 16) {
        display.innerText = "Large";
    } else {
        display.innerText = "Small";
    }
}

function getSelectedLanguage() {
    const radios = document.getElementsByName('language');
    for (let r of radios) {
        if (r.checked) return r.value;
    }
    return 'English';
}

function updateSettings() {
    console.log("Language setting changed to: " + getSelectedLanguage());
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const msg = input.value.trim();
    if (!msg) return;

    appendMessage(msg, 'user');
    input.value = '';

    const lang = getSelectedLanguage(); 

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                message: msg, 
                patient_id: currentPatientId,
                language: lang 
            })
        });
        
        const data = await response.json();

        if (data.error) {
            appendMessage("Error: " + data.error, 'ai');
            console.error("Server Error:", data.error);
        } else if (data.response) {
            appendMessage(data.response, 'ai');
        } else {
            appendMessage("System Error: No response received.", 'ai');
        }

    } catch (error) {
        appendMessage("Network Error: Could not connect to server.", 'ai');
        console.error(error);
    }
}

function appendMessage(text, sender) {
    const box = document.getElementById('chat-box');
    const div = document.createElement('div');
    div.classList.add('msg', sender);
    div.innerText = text;
    box.appendChild(div);
    
    box.scrollTop = box.scrollHeight;
}

async function resetSession() {
    if(!confirm("Are you sure? This will clear the chat and save the log for moderators.")) return;

    try {
        await fetch('/reset', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ patient_id: currentPatientId })
        });

        alert("Session log saved successfully.");
        
        document.getElementById('chat-box').innerHTML = '';
        document.getElementById('user-input').value = '';
        
        selectPatient(currentPatientId, document.getElementById('btn-' + currentPatientId).innerText);
        
    } catch (error) {
        alert("Error resetting session. Check console.");
        console.error(error);
    }
}

document.getElementById("user-input").addEventListener("keypress", function(event) {
  if (event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
});