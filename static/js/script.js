// Tabs & Form Elements
const loginTab = document.getElementById('loginTab');
const signupTab = document.getElementById('signupTab');
const nameField = document.getElementById('nameField');
const submitBtn = document.getElementById('mainSubmit');
const authForm = document.getElementById('authForm');

// Input fields
const nameInput = document.getElementById('name');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');

// -------------------------------
// Switch between Login and Signup
// -------------------------------
function setMode(mode) {
    if (mode === 'signup') {
        signupTab.classList.add('active');
        loginTab.classList.remove('active');
        nameField.classList.remove('hidden');
        submitBtn.textContent = 'Create account';
    } else {
        loginTab.classList.add('active');
        signupTab.classList.remove('active');
        nameField.classList.add('hidden');
        submitBtn.textContent = 'Log in';
    }
}

loginTab.addEventListener('click', () => setMode('login'));
signupTab.addEventListener('click', () => setMode('signup'));

// -------------------------------
// Handle Form Submission
// -------------------------------
authForm.addEventListener('submit', function (e) {
    e.preventDefault();

    // Detect mode
    const mode = signupTab.classList.contains('active') ? 'signup' : 'login';

    // Get role
    const role = document.querySelector('input[name="role"]:checked').value;

    // Create form data
    const formData = new FormData();
    formData.append('mode', mode);
    formData.append('email', emailInput.value);
    formData.append('password', passwordInput.value);
    formData.append('role', role);

    // Add name only during signup
    if (mode === 'signup') {
        if (!nameInput.value.trim()) {
            alert("Please enter your full name");
            return;
        }
        formData.append('name', nameInput.value);
    }

    // Send data to Flask backend
    fetch('/auth', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        // Flask redirects → browser redirect
        if (response.redirected) {
            window.location.href = response.url;
            return;
        }
        return response.text();
    })
    .then(data => {
        if (data) {
            alert(data);
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("Server error. Please try again.");
    });
});
