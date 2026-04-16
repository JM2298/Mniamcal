const express = require('express');
const session = require('express-session');
const path = require('path');
const axios = require('axios');
const engine = require('ejs-locals');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const API_BASE_URL = process.env.API_BASE_URL || 'https://dieta-backend.michalowicz.dev';

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.use(session({
    secret: process.env.SESSION_SECRET || 'default_secret_key',
    resave: false,
    saveUninitialized: false,
    cookie: { 
        secure: true,
        maxAge: 24 * 60 * 60 * 1000
    }
}));

app.engine('ejs', engine);
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use((req, res, next) => {
    res.locals.user = req.session.user || null;
    res.locals.error = req.session.error || null;
    res.locals.success = req.session.success || null;
    delete req.session.error;
    delete req.session.success;
    next();
});

const requireAuth = (req, res, next) => {
    if (!req.session.accessToken) {
        req.session.error = 'Musisz być zalogowany, aby uzyskać dostęp do tej strony.';
        return res.redirect('/login');
    }
    next();
};

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json'
    }
});

const authApiClient = (token) => axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    }
});

app.get('/', (req, res) => {
    res.render('index');
});

app.get('/login', (req, res) => {
    if (req.session.accessToken) {
        return res.redirect('/dashboard');
    }
    res.render('login');
});

app.post('/login', async (req, res) => {
    const { username, password } = req.body;
    
    try {
        const response = await apiClient.post('/api/auth/login/', {
            username,
            password
        });
        
        if (response.data.access) {
            const userResponse = await authApiClient(response.data.access).get('/api/auth/me/');
            
            req.session.accessToken = response.data.access;
            req.session.refreshToken = response.data.refresh;
            req.session.user = userResponse.data.results?.[0] || userResponse.data;
            req.session.success = 'Zalogowano pomyślnie!';
            
            res.redirect('/dashboard');
        }
    } catch (error) {
        console.error('Login error:', error.response?.data || error.message);
        req.session.error = error.response?.data?.detail || 'Nieprawidłowa nazwa użytkownika lub hasło';
        res.redirect('/login');
    }
});

app.get('/register', (req, res) => {
    if (req.session.accessToken) {
        return res.redirect('/dashboard');
    }
    res.render('register');
});

app.post('/register', async (req, res) => {
    const { username, first_name, email, password, password_confirm } = req.body;
    
    if (password !== password_confirm) {
        req.session.error = 'Hasła nie są identyczne';
        return res.redirect('/register');
    }
    
    try {
        const response = await apiClient.post('/api/auth/register/', {
            username,
            first_name,
            email,
            password
        });
        
        if (response.data.access) {
            req.session.accessToken = response.data.access;
            req.session.refreshToken = response.data.refresh;
            req.session.user = { username, first_name, email };
            req.session.success = 'Rejestracja zakończona sukcesem!';
            
            res.redirect('/dashboard');
        }
    } catch (error) {
        console.error('Register error:', error.response?.data || error.message);
        
        let errorMessage = 'Błąd podczas rejestracji';
        if (error.response?.data) {
            if (typeof error.response.data === 'object') {
                const errors = [];
                Object.entries(error.response.data).forEach(([key, value]) => {
                    errors.push(`${key}: ${value}`);
                });
                errorMessage = errors.join(', ');
            } else {
                errorMessage = error.response.data.detail || errorMessage;
            }
        }
        
        req.session.error = errorMessage;
        res.redirect('/register');
    }
});

app.get('/logout', (req, res) => {
    req.session.destroy((err) => {
        if (err) {
            console.error('Logout error:', err);
        }
        res.redirect('/');
    });
});

app.get('/dashboard', requireAuth, async (req, res) => {
    try {
        const api = authApiClient(req.session.accessToken);
        
        const userResponse = await api.get('/api/auth/me/');
        const userData = userResponse.data.results?.[0] || userResponse.data;
        
        let familyData = null;
        try {
            const familyResponse = await api.get('/api/families/my-membership/');
            familyData = familyResponse.data;
        } catch (error) {
            console.log('Użytkownik nie ma jeszcze rodziny');
        }
        
        res.render('dashboard', {
            user: userData,
            family: familyData
        });
    } catch (error) {
        console.error('Dashboard error:', error.response?.data || error.message);
        
        if (error.response?.status === 401) {
            req.session.error = 'Sesja wygasła, zaloguj się ponownie';
            return res.redirect('/login');
        }
        
        req.session.error = 'Błąd podczas ładowania dashboardu';
        res.render('dashboard', { user: req.session.user, family: null });
    }
});

app.listen(PORT, () => {
    console.log(`Strona działa na http://localhost:${PORT}`);
    console.log(`API URL: ${API_BASE_URL}`);
});