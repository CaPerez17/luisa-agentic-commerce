const API_URL = 'http://localhost:8000';
let conversationId = generateConversationId();
let isTyping = false;

// Generar ID de conversación único
function generateConversationId() {
    return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Elementos del DOM
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const chatView = document.getElementById('chatView');
const internalView = document.getElementById('internalView');
const toggleViewButton = document.getElementById('toggleView');
const backToChatButton = document.getElementById('backToChat');
const handoffsContainer = document.getElementById('handoffsContainer');

// Event listeners
sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

toggleViewButton.addEventListener('click', toggleView);
backToChatButton.addEventListener('click', () => {
    chatView.classList.remove('hidden');
    internalView.classList.add('hidden');
});

// Enviar mensaje
async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isTyping) return;
    
    // Mostrar mensaje del cliente
    addMessage(text, 'customer');
    messageInput.value = '';
    sendButton.disabled = true;
    
    // Mostrar indicador de escritura
    showTypingIndicator();
    isTyping = true;
    
    try {
        const response = await fetch(`${API_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: conversationId,
                text: text,
                sender: 'customer'
            })
        });
        
        const data = await response.json();
        
        // Simular tiempo de escritura natural basado en longitud del mensaje
        // Base: 1.2s + 0.05s por carácter + variación aleatoria
        const messageLength = data.response.length;
        const baseTime = 1200;
        const charTime = messageLength * 50;
        const randomVariation = Math.random() * 800; // 0-800ms adicionales
        const typingTime = baseTime + charTime + randomVariation;
        
        // Mínimo 1.5s, máximo 4s para mantener naturalidad
        const finalTypingTime = Math.max(1500, Math.min(4000, typingTime));
        
        setTimeout(() => {
            hideTypingIndicator();
            addMessage(data.response, 'luisa');
            
            // Si hay asset, agregarlo como mensaje separado
            if (data.asset && data.asset.asset_url) {
                addAssetMessage(data.asset, 'luisa');
            }
            
            isTyping = false;
            sendButton.disabled = false;
            messageInput.focus();
        }, finalTypingTime);
        
    } catch (error) {
        console.error('Error:', error);
        hideTypingIndicator();
        addMessage('Disculpa, hubo un problema. ¿Puedes intentar de nuevo?', 'luisa');
        isTyping = false;
        sendButton.disabled = false;
    }
}

// Agregar mensaje al chat
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();
    
    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(timeDiv);
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

// Agregar asset (imagen o video) al chat
function addAssetMessage(asset, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const assetContainer = document.createElement('div');
    assetContainer.className = 'message-asset';
    
    const assetUrl = `${API_URL}${asset.asset_url}`;
    
    if (asset.type === 'image') {
        const img = document.createElement('img');
        img.src = assetUrl;
        img.alt = 'Imagen enviada';
        img.className = 'asset-image';
        img.onerror = function() {
            // Si falla la carga, ocultar el elemento sin romper el chat
            this.style.display = 'none';
        };
        assetContainer.appendChild(img);
    } else if (asset.type === 'video') {
        const video = document.createElement('video');
        video.src = assetUrl;
        video.controls = true;
        video.className = 'asset-video';
        video.onerror = function() {
            // Si falla la carga, ocultar el elemento sin romper el chat
            this.style.display = 'none';
        };
        assetContainer.appendChild(video);
    }
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();
    
    messageDiv.appendChild(assetContainer);
    messageDiv.appendChild(timeDiv);
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

// Mostrar indicador de escritura
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.id = 'typingIndicator';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'typing-dot';
        typingDiv.appendChild(dot);
    }
    
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
}

// Ocultar indicador de escritura
function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Obtener hora actual formateada
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

// Scroll al final
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Alternar vista
function toggleView() {
    const isChatVisible = !chatView.classList.contains('hidden');
    
    if (isChatVisible) {
        chatView.classList.add('hidden');
        internalView.classList.remove('hidden');
        loadHandoffs();
    } else {
        chatView.classList.remove('hidden');
        internalView.classList.add('hidden');
    }
}

// Cargar handoffs
async function loadHandoffs() {
    handoffsContainer.innerHTML = '<div class="loading">Cargando handoffs...</div>';
    
    try {
        const response = await fetch(`${API_URL}/api/handoffs`);
        const handoffs = await response.json();
        
        if (handoffs.length === 0) {
            handoffsContainer.innerHTML = '<div class="empty-state">No hay handoffs aún</div>';
            return;
        }
        
        handoffsContainer.innerHTML = '';
        
        handoffs.forEach(handoff => {
            const card = createHandoffCard(handoff);
            handoffsContainer.appendChild(card);
        });
        
    } catch (error) {
        console.error('Error cargando handoffs:', error);
        handoffsContainer.innerHTML = '<div class="empty-state">Error al cargar handoffs</div>';
    }
}

// Crear tarjeta de handoff
function createHandoffCard(handoff) {
    const card = document.createElement('div');
    card.className = 'handoff-card';
    
    const priorityClass = `priority-${handoff.priority}`;
    
    card.innerHTML = `
        <div class="handoff-header">
            <div>
                <div class="handoff-reason">${escapeHtml(handoff.reason)}</div>
                ${handoff.customer_name ? `<div style="font-size: 12px; color: #666; margin-top: 4px;">Cliente: ${escapeHtml(handoff.customer_name)}</div>` : ''}
            </div>
            <span class="priority-badge ${priorityClass}">${handoff.priority}</span>
        </div>
        
        <div class="handoff-summary">${escapeHtml(handoff.summary)}</div>
        
        <div class="handoff-suggested">
            <div class="handoff-suggested-label">💡 Próxima respuesta sugerida:</div>
            <div class="handoff-suggested-text">${escapeHtml(handoff.suggested_response)}</div>
        </div>
        
        <div class="handoff-meta">
            <div>Conversación: ${handoff.conversation_id}</div>
            <div>${formatTimestamp(handoff.timestamp)}</div>
        </div>
    `;
    
    return card;
}

// Escapar HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Formatear timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Inicializar
messageInput.focus();

