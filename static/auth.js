// Initialize Supabase client
const supabaseUrl = 'your_supabase_url';
const supabaseKey = 'your_supabase_anon_key';
const supabase = supabase.createClient(supabaseUrl, supabaseKey);

const msgDiv = document.getElementById('msg');
const forms = {
    login: document.getElementById('login-form'),
    register: document.getElementById('register-form'),
    forgot: document.getElementById('forgot-form'),
    reset: document.getElementById('reset-form')
};
const dashboard = document.getElementById('dashboard');

let currentForm = 'login';

// Form switching
document.getElementById('goto-register').addEventListener('click', () => switchForm('register'));
document.getElementById('goto-login').addEventListener('click', () => switchForm('login'));
document.getElementById('goto-forgot').addEventListener('click', () => switchForm('forgot'));
document.getElementById('goto-login2').addEventListener('click', () => switchForm('login'));
document.getElementById('goto-login3').addEventListener('click', () => switchForm('login'));

function switchForm(form) {
    Object.keys(forms).forEach(f => forms[f].classList.add('hidden'));
    forms[form].classList.remove('hidden');
    currentForm = form;
    document.getElementById('form-title').textContent = form === 'login' ? 'Welcome Back' : 
        form === 'register' ? 'Create Account' : 
        form === 'forgot' ? 'Forgot Password' : 'Reset Password';
}

// Login
forms.login.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
        showMessage(error.message, 'error');
    } else {
        const token = data.session.access_token;
        fetch('/verify-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        }).then(res => res.json()).then(data => {
            if (data.status === 'success') {
                sessionStorage.setItem('token', token);
                sessionStorage.setItem('user', JSON.stringify(data.user));
                window.location.href = '/user-select'; // Redirect to user selection
            } else {
                showMessage('Authentication failed', 'error');
            }
        });
    }
});

// Register
forms.register.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const password2 = document.getElementById('register-pass2').value;
    const fullName = document.getElementById('register-fullname').value;

    if (password !== password2) {
        showMessage('Passwords do not match', 'error');
        return;
    }

    const { data, error } = await supabase.auth.signUp({ email, password, options: { data: { full_name: fullName } } });
    if (error) showMessage(error.message, 'error');
    else {
        showMessage('Check your email for verification link', 'success');
        const token = data.session?.access_token; // Handle case where session is not immediate
        if (token) {
            sessionStorage.setItem('token', token);
            sessionStorage.setItem('user', JSON.stringify(data.user));
            window.location.href = '/user-select';
        }
    }
});

// Forgot Password
forms.forgot.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('forgot-email').value;
    const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.origin + '/reset'
    });
    if (error) showMessage(error.message, 'error');
    else showMessage('Check your email for reset link', 'success');
});

// Reset Password
forms.reset.addEventListener('submit', async (e) => {
    e.preventDefault();
    const newPassword = document.getElementById('reset-password').value;
    const newPassword2 = document.getElementById('reset-pass2').value;

    if (newPassword !== newPassword2) {
        showMessage('Passwords do not match', 'error');
        return;
    }

    const { data, error } = await supabase.auth.updateUser({ password: newPassword });
    if (error) showMessage(error.message, 'error');
    else {
        showMessage('Password updated successfully', 'success');
        switchForm('login');
    }
});

function logout() {
    supabase.auth.signOut();
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    switchForm('login');
}

function showMessage(message, type) {
    msgDiv.textContent = message;
    msgDiv.className = `msg ${type}`;
}

function updateDashboard(user) {
    document.getElementById('user-name').textContent = user.user_metadata.full_name || 'User';
    document.getElementById('user-email').textContent = user.email;
    document.getElementById('avatar').textContent = (user.user_metadata.full_name || 'TM')[0];
}

// Check auth state on load
document.addEventListener('DOMContentLoaded', () => {
    const token = sessionStorage.getItem('token');
    const user = JSON.parse(sessionStorage.getItem('user'));
    if (token && user) {
        fetch('/verify-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        }).then(res => res.json()).then(data => {
            if (data.status === 'success') {
                switchForm('dashboard');
                updateDashboard(user);
            }
        });
    }
});