// API Base URLs (override via admin-ui/config.js)
const CONFIG = window.MICROSERVICES_CONFIG || {};
const AUTH_BASE_URL = CONFIG.authBaseUrl || 'http://localhost:3101';
const PEOPLE_BASE_URL = CONFIG.peopleBaseUrl || 'http://localhost:3002';
const CASES_BASE_URL = CONFIG.caseBaseUrl || 'http://localhost:3003';

const AUTH_URL = `${AUTH_BASE_URL}/api/auth`;
const PEOPLE_URL = `${PEOPLE_BASE_URL}/api/people`;
const CASES_URL = `${CASES_BASE_URL}/api/cases`;

// Store JWT token
let jwtToken = localStorage.getItem('jwt_token') || null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Microservices Admin UI loaded');
    console.log('📌 Make sure all services are running:');
    console.log(`   - Auth Service: ${AUTH_BASE_URL}`);
    console.log(`   - People Service: ${PEOPLE_BASE_URL}`);
    console.log(`   - Case Service: ${CASES_BASE_URL}`);
    
    checkServicesOnLoad();
    
    if (jwtToken) {
        showMainContent();
        verifyToken();
    }
});

// Check if Auth service is reachable on load
async function checkServicesOnLoad() {
    const warning = document.getElementById('services-warning');
    try {
        const r = await fetch(`${AUTH_BASE_URL}/health`, { method: 'GET' });
        if (r.ok) {
            warning.style.display = 'none';
            return;
        }
    } catch (e) {}
    warning.style.display = 'block';
}

// Helper: Show result message
function showResult(elementId, message, isSuccess = true) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `result ${isSuccess ? 'success' : 'error'}`;
    setTimeout(() => {
        element.className = 'result';
    }, 5000);
}

// Helper: API call with error handling
async function apiCall(url, options = {}) {
    try {
        console.log(`📡 API Call: ${options.method || 'GET'} ${url}`);
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(jwtToken && { 'Authorization': `Bearer ${jwtToken}` }),
                ...options.headers,
            },
        });

        const data = await response.json();
        console.log(`✅ Response:`, data);

        if (!response.ok) {
            throw new Error(data.error || data.message || 'Request failed');
        }

        return data;
    } catch (error) {
        console.error('❌ API Error:', error);
        throw error;
    }
}

// Register
async function register() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const full_name = document.getElementById('full_name').value;

    try {
        const data = await apiCall(`${AUTH_URL}/register`, {
            method: 'POST',
            body: JSON.stringify({ email, password, full_name }),
        });

        showResult('login-result', `✅ User registered: ${data.data.email}`, true);
    } catch (error) {
        const msg = error.message === 'Failed to fetch' 
            ? 'Services chưa chạy! Xem hộp cảnh báo màu đỏ phía trên và chạy 3 lệnh trong 3 PowerShell.'
            : `❌ Register failed: ${error.message}`;
        showResult('login-result', msg, false);
    }
}

// Login
async function login() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
        const data = await apiCall(`${AUTH_URL}/login`, {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });

        jwtToken = data.data.token;
        localStorage.setItem('jwt_token', jwtToken);
        
        showResult('login-result', `✅ Login successful!`, true);
        showMainContent();
        
        document.getElementById('user-email').textContent = data.data.user.email;
    } catch (error) {
        const msg = error.message === 'Failed to fetch' 
            ? 'Services chưa chạy! Xem hộp cảnh báo màu đỏ phía trên và chạy 3 lệnh trong 3 PowerShell.'
            : `❌ Login failed: ${error.message}`;
        showResult('login-result', msg, false);
    }
}

// Verify token
async function verifyToken() {
    try {
        const data = await apiCall(`${AUTH_URL}/profile`);
        document.getElementById('user-email').textContent = data.data.email;
    } catch (error) {
        logout();
    }
}

// Logout
function logout() {
    jwtToken = null;
    localStorage.removeItem('jwt_token');
    document.getElementById('login-section').style.display = 'block';
    document.getElementById('main-content').style.display = 'none';
    document.getElementById('user-info').style.display = 'none';
}

// Show main content
function showMainContent() {
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('main-content').style.display = 'block';
    document.getElementById('user-info').style.display = 'flex';
}

// Create Person
async function createPerson() {
    const person = {
        first_name: document.getElementById('first_name').value,
        last_name: document.getElementById('last_name').value,
        email: document.getElementById('person_email').value,
        phone: document.getElementById('phone').value,
        address: document.getElementById('address').value,
    };

    try {
        const data = await apiCall(PEOPLE_URL, {
            method: 'POST',
            body: JSON.stringify(person),
        });

        showResult('create-person-result', `✅ Person created: ${data.data.first_name} ${data.data.last_name} (ID: ${data.data.id})`, true);
        console.log('🎉 Kafka event published: people.created');
        listPeople();
    } catch (error) {
        showResult('create-person-result', `❌ Failed: ${error.message}`, false);
    }
}

// List People
async function listPeople() {
    try {
        console.log('📊 Fetching people list...');
        const data = await apiCall(`${PEOPLE_URL}?page=1&limit=10`);

        const listDiv = document.getElementById('people-list');
        
        if (data.data.data.length === 0) {
            listDiv.innerHTML = '<p class="info-text">No people found. Create one above!</p>';
            return;
        }

        listDiv.innerHTML = data.data.data.map(person => `
            <div class="item">
                <div class="item-header">
                    <div class="item-title">${person.first_name} ${person.last_name}</div>
                    <div class="item-id">ID: ${person.id}</div>
                </div>
                <div class="item-body">
                    📧 ${person.email || 'N/A'}<br>
                    📞 ${person.phone || 'N/A'}<br>
                    📍 ${person.address || 'N/A'}<br>
                    <small>Created: ${new Date(person.created_at).toLocaleString()}</small>
                </div>
            </div>
        `).join('');

        console.log('💡 TIP: Call this API again to see Redis cache hit!');
    } catch (error) {
        document.getElementById('people-list').innerHTML = `<p class="result error">❌ ${error.message}</p>`;
    }
}

// Create Case
async function createCase() {
    const caseData = {
        title: document.getElementById('case_title').value,
        description: document.getElementById('case_description').value,
        status: document.getElementById('case_status').value,
        priority: document.getElementById('case_priority').value,
        person_id: document.getElementById('person_id').value ? parseInt(document.getElementById('person_id').value) : undefined,
    };

    try {
        const data = await apiCall(CASES_URL, {
            method: 'POST',
            body: JSON.stringify(caseData),
        });

        showResult('create-case-result', `✅ Case created: ${data.data.case_number} (ID: ${data.data.id})`, true);
        console.log('🔍 Case auto-indexed to Elasticsearch!');
        listCases();
    } catch (error) {
        showResult('create-case-result', `❌ Failed: ${error.message}`, false);
    }
}

// Search Cases
async function searchCases() {
    const query = document.getElementById('search_query').value;
    const status = document.getElementById('search_status').value;
    const priority = document.getElementById('search_priority').value;

    const params = new URLSearchParams();
    if (query) params.append('q', query);
    if (status) params.append('status', status);
    if (priority) params.append('priority', priority);

    try {
        console.log('🔍 Searching with Elasticsearch...');
        const data = await apiCall(`${CASES_URL}/search?${params}`);

        const resultDiv = document.getElementById('search-result');
        
        if (data.data.length === 0) {
            resultDiv.innerHTML = '<p class="info-text">No results found</p>';
            return;
        }

        resultDiv.innerHTML = `
            <p class="info-text">Found ${data.data.length} results</p>
            ${data.data.map(caseItem => renderCase(caseItem)).join('')}
        `;

        console.log('✅ Elasticsearch search completed!');
    } catch (error) {
        document.getElementById('search-result').innerHTML = `<p class="result error">❌ ${error.message}</p>`;
    }
}

// List Cases
async function listCases() {
    try {
        const data = await apiCall(`${CASES_URL}?page=1&limit=10`);

        const listDiv = document.getElementById('cases-list');
        
        if (data.data.data.length === 0) {
            listDiv.innerHTML = '<p class="info-text">No cases found. Create one above!</p>';
            return;
        }

        listDiv.innerHTML = data.data.data.map(caseItem => renderCase(caseItem)).join('');
    } catch (error) {
        document.getElementById('cases-list').innerHTML = `<p class="result error">❌ ${error.message}</p>`;
    }
}

// Render case item
function renderCase(caseItem) {
    return `
        <div class="item">
            <div class="item-header">
                <div>
                    <div class="item-title">${caseItem.title}</div>
                    <div class="item-id">${caseItem.case_number}</div>
                </div>
                <div>
                    <span class="badge badge-${caseItem.status}">${caseItem.status}</span>
                    <span class="badge badge-${caseItem.priority}">${caseItem.priority}</span>
                </div>
            </div>
            <div class="item-body">
                ${caseItem.description || 'No description'}<br>
                <small>Person ID: ${caseItem.person_id || 'N/A'} | Created: ${new Date(caseItem.created_at).toLocaleString()}</small>
            </div>
        </div>
    `;
}

// Check Health
async function checkHealth() {
    const resultDiv = document.getElementById('health-result');
    resultDiv.innerHTML = '<p>Checking services...</p>';

    const services = [
        { name: 'Auth Service', url: `${AUTH_BASE_URL}/health` },
        { name: 'People Service', url: `${PEOPLE_BASE_URL}/health` },
        { name: 'Case Service', url: `${CASES_BASE_URL}/health` },
    ];

    let html = '';
    for (const service of services) {
        try {
            const response = await fetch(service.url);
            const data = await response.json();
            html += `
                <div class="health-item">
                    <span>${service.name}</span>
                    <span class="status-ok">✅ ${data.status}</span>
                </div>
            `;
        } catch (error) {
            html += `
                <div class="health-item">
                    <span>${service.name}</span>
                    <span class="status-error">❌ Offline</span>
                </div>
            `;
        }
    }

    resultDiv.innerHTML = html;
}
