const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');
const axios = require('axios');
const expressLayouts = require('express-ejs-layouts');
const jwt = require('jsonwebtoken');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const API_BASE_URL = process.env.API_BASE_URL || 'https://dieta-backend.michalowicz.dev';
const JWT_SECRET = process.env.JWT_SECRET || 'dev_jwt_secret_change_me';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '1d';
const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const AUTH_COOKIE_NAME = 'auth_token';

const BASE_COOKIE_OPTIONS = {
    httpOnly: true,
    sameSite: 'lax',
    secure: IS_PRODUCTION
};

const AUTH_COOKIE_OPTIONS = {
    ...BASE_COOKIE_OPTIONS,
    maxAge: 24 * 60 * 60 * 1000
};

const FLASH_COOKIE_OPTIONS = {
    ...BASE_COOKIE_OPTIONS,
    maxAge: 30 * 1000
};

const setFlash = (res, type, message) => {
    if (!message) {
        return;
    }

    const cookieName = type === 'error' ? 'flash_error' : 'flash_success';
    res.cookie(cookieName, message, FLASH_COOKIE_OPTIONS);
};

const clearFlash = (req, res) => {
    if (req.cookies.flash_error) {
        res.clearCookie('flash_error', BASE_COOKIE_OPTIONS);
    }
    if (req.cookies.flash_success) {
        res.clearCookie('flash_success', BASE_COOKIE_OPTIONS);
    }
};

const clearAuthCookie = (res) => {
    res.clearCookie(AUTH_COOKIE_NAME, BASE_COOKIE_OPTIONS);
};

const createAuthToken = (accessToken, refreshToken, user) => jwt.sign({
    accessToken,
    refreshToken,
    user: {
        id: user?.id,
        username: user?.username,
        first_name: user?.first_name,
        email: user?.email
    }
}, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(expressLayouts);
app.set('layout', 'layout');

app.use((req, res, next) => {
    req.auth = null;

    const authToken = req.cookies[AUTH_COOKIE_NAME];
    if (authToken) {
        try {
            req.auth = jwt.verify(authToken, JWT_SECRET);
        } catch (error) {
            clearAuthCookie(res);
        }
    }

    res.locals.user = req.auth?.user || null;
    res.locals.error = req.cookies.flash_error || null;
    res.locals.success = req.cookies.flash_success || null;
    clearFlash(req, res);
    next();
});

const requireAuth = (req, res, next) => {
    if (!req.auth?.accessToken) {
        setFlash(res, 'error', 'Musisz być zalogowany, aby uzyskać dostęp do tej strony.');
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
    if (req.auth?.accessToken) {
        return res.redirect('/dashboard');
    }
    res.render('index', { title: 'Witaj w Mniamcal' });
});

app.get('/diets', async (req, res) => {
    try {
        const response = await apiClient.get('/api/diets/');
        const diets = response.data.results || response.data;
        
        res.render('diets', { 
            title: 'Lista Diet',
            diets: diets,
            isAuthenticated: !!req.auth?.accessToken
        });
    } catch (error) {
        console.error('Diets error:', error.response?.data || error.message);
        setFlash(res, 'error', 'Błąd podczas ładowania listy diet');
        res.render('diets', { 
            title: 'Lista Diet',
            diets: [],
            isAuthenticated: !!req.auth?.accessToken,
            error: 'Nie udało się wczytać listy diet'
        });
    }
});

app.get('/login', (req, res) => {
    if (req.auth?.accessToken) {
        return res.redirect('/dashboard');
    }
    res.render('login', { title: 'Logowanie' });
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
            const userData = userResponse.data.results?.[0] || userResponse.data;
            const authToken = createAuthToken(response.data.access, response.data.refresh, userData);
            
            res.cookie(AUTH_COOKIE_NAME, authToken, AUTH_COOKIE_OPTIONS);
            setFlash(res, 'success', 'Zalogowano pomyślnie!');
            return res.redirect('/dashboard');
        }
            
        setFlash(res, 'error', 'Nie udało się zalogować użytkownika.');
        res.redirect('/login');
    } catch (error) {
        console.error('Login error:', error.response?.data || error.message);
        setFlash(res, 'error', error.response?.data?.detail || 'Nieprawidłowa nazwa użytkownika lub hasło');
        res.redirect('/login');
    }
});

app.get('/register', (req, res) => {
    if (req.auth?.accessToken) {
        return res.redirect('/dashboard');
    }
    res.render('register', { title: 'Rejestracja' });
});

app.post('/register', async (req, res) => {
    const { username, first_name, email, password, password_confirm } = req.body;
    
    if (password !== password_confirm) {
        setFlash(res, 'error', 'Hasła nie są identyczne');
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
            let userData = { username, first_name, email };

            try {
                const userResponse = await authApiClient(response.data.access).get('/api/auth/me/');
                userData = userResponse.data.results?.[0] || userResponse.data || userData;
            } catch (profileError) {
                console.warn('Register profile fetch warning:', profileError.response?.data || profileError.message);
            }

            const authToken = createAuthToken(response.data.access, response.data.refresh, userData);

            res.cookie(AUTH_COOKIE_NAME, authToken, AUTH_COOKIE_OPTIONS);
            setFlash(res, 'success', 'Rejestracja zakończona sukcesem!');
            return res.redirect('/dashboard');
        }

        setFlash(res, 'error', 'Nie udało się zarejestrować użytkownika.');
        res.redirect('/register');
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
        
        setFlash(res, 'error', errorMessage);
        res.redirect('/register');
    }
});

app.get('/logout', (req, res) => {
    clearAuthCookie(res);
    clearFlash(req, res);
    res.redirect('/');
});

app.get('/dashboard', requireAuth, async (req, res) => {
    try {
        const api = authApiClient(req.auth.accessToken);
        
        const userResponse = await api.get('/api/auth/me/');
        const userData = userResponse.data.results?.[0] || userResponse.data;
        
        let familyData = null;
        try {
            const familyResponse = await api.get('/api/families/members/');
            const memberData = familyResponse.data;
            if (memberData && memberData.rodzina_id) {
                familyData = {
                    rodzina_id: memberData.rodzina_id,
                    rodzina: memberData.rodzina,
                    is_founder: memberData.members?.[0]?.is_founder || false
                };
            }
        } catch (error) {
            console.log('Użytkownik nie ma jeszcze rodziny');
        }
        
        res.render('dashboard', {
            title: 'Dashboard',
            user: userData,
            family: familyData
        });
    } catch (error) {
        console.error('Dashboard error:', error.response?.data || error.message);
        
        if (error.response?.status === 401) {
            clearAuthCookie(res);
            setFlash(res, 'error', 'Sesja wygasła, zaloguj się ponownie');
            return res.redirect('/login');
        }
        
        setFlash(res, 'error', 'Błąd podczas ładowania dashboardu');
        res.render('dashboard', { title: 'Dashboard', user: req.auth?.user || null, family: null });
    }
});

app.post('/create-family', requireAuth, async (req, res) => {
    const { family_name } = req.body;

    if (!family_name || family_name.trim() === '') {
        setFlash(res, 'error', 'Nazwa rodziny nie może być pusta');
        return res.redirect('/dashboard');
    }

    try {
        const api = authApiClient(req.auth.accessToken);
        
        const response = await api.post('/api/families/', {
            rodzina: family_name.trim()
        });

        if (response.status === 201 || response.status === 200) {
            setFlash(res, 'success', `Rodzina "${family_name}" została utworzona!`);
            return res.redirect('/dashboard');
        }

        setFlash(res, 'error', 'Nie udało się utworzyć rodziny');
        res.redirect('/dashboard');
    } catch (error) {
        console.error('Create family error:', error.response?.data || error.message);
        
        if (error.response?.status === 401) {
            clearAuthCookie(res);
            setFlash(res, 'error', 'Sesja wygasła, zaloguj się ponownie');
            return res.redirect('/login');
        }

        let errorMessage = 'Błąd podczas tworzenia rodziny';
        if (error.response?.data?.rodzina) {
            errorMessage = error.response.data.rodzina[0] || errorMessage;
        } else if (error.response?.data?.detail) {
            errorMessage = error.response.data.detail;
        }

        setFlash(res, 'error', errorMessage);
        res.redirect('/dashboard');
    }
});

app.listen(PORT, () => {
    console.log(`Strona działa na http://localhost:${PORT}`);
    console.log(`API URL: ${API_BASE_URL}`);
});