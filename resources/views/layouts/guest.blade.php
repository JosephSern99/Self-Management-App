<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>{{ config('app.name', 'Finance Manager') }} — Sign In</title>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

    @vite(['resources/css/app.css', 'resources/js/app.js'])

    <style>
        body {
            margin: 0;
            min-height: 100vh;
            font-family: 'Plus Jakarta Sans', 'Segoe UI', system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        .login-bg {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(160deg, #060b1a 0%, #0d1535 25%, #1a0d35 45%, #2d0f1a 65%, #180a12 80%, #060b1a 100%);
            padding: 24px;
            position: relative;
            overflow: hidden;
        }

        /* Ambient blue-red orbs */
        .orb { position: absolute; border-radius: 50%; pointer-events: none; }

        .orb-tr {
            top: -10%; right: -5%;
            width: 560px; height: 560px;
            background: radial-gradient(circle, rgba(59,130,246,0.28) 0%, rgba(37,99,235,0.12) 40%, transparent 70%);
            animation: float 7s ease-in-out infinite;
            filter: blur(40px);
        }

        .orb-bl {
            bottom: -12%; left: -6%;
            width: 480px; height: 480px;
            background: radial-gradient(circle, rgba(220,38,38,0.25) 0%, rgba(185,28,28,0.1) 45%, transparent 70%);
            animation: float 9s ease-in-out infinite 2s;
            filter: blur(50px);
        }

        .orb-mid {
            top: 40%; left: 12%;
            width: 200px; height: 200px;
            background: radial-gradient(circle, rgba(124,58,237,0.2) 0%, transparent 70%);
            animation: float 6s ease-in-out infinite 1s, pulseGlow 4s ease-in-out infinite;
            filter: blur(30px);
        }

        /* Top blue-to-red streak */
        .teal-streak {
            position: absolute; top: 0; left: 20%; right: 20%;
            height: 2px;
            background: linear-gradient(90deg, transparent 0%, #3b82f6 35%, #7c3aed 60%, #ef4444 85%, transparent 100%);
            opacity: 0.5;
        }

        /* Grid overlay */
        .grid-overlay {
            position: absolute; inset: 0; opacity: 0.03;
            background-image:
                linear-gradient(rgba(96,165,250,0.2) 1px, transparent 1px),
                linear-gradient(90deg, rgba(96,165,250,0.2) 1px, transparent 1px);
            background-size: 60px 60px;
        }

        /* Login card */
        .login-card {
            width: 100%;
            max-width: 420px;
            background: linear-gradient(180deg, #ffffff 0%, #fafbfd 100%);
            border-radius: 18px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 8px 40px rgba(0,0,0,0.14), 0 0 60px rgba(37,99,235,0.06), inset 0 1px 0 rgba(255,255,255,0.9);
            padding: 40px 36px;
            position: relative;
            z-index: 1;
            animation: fadeInUp 0.45s ease both;
        }

        /* Logo area */
        .login-logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .login-logo-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 52px; height: 52px;
            background: linear-gradient(135deg, #2563eb 0%, #dc2626 100%);
            border-radius: 14px;
            box-shadow: 0 4px 16px rgba(37,99,235,0.3);
            margin-bottom: 14px;
        }

        .login-logo-title {
            font-size: 22px;
            font-weight: 900;
            color: #0f172a;
            letter-spacing: -0.5px;
        }

        .login-logo-subtitle {
            font-size: 13px;
            color: #64748b;
            font-weight: 500;
            margin-top: 4px;
        }

        /* Form elements */
        .login-label {
            display: block;
            font-size: 11px; font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
        }

        .login-input-wrap { position: relative; }

        .login-input {
            width: 100%;
            padding: 11px 14px;
            border: 1.5px solid #e2e8f0;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit; font-weight: 500;
            color: #0f172a;
            background: white;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
            box-sizing: border-box;
        }

        .login-input:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 3px rgba(37,99,235,0.13);
        }

        .login-input.has-toggle { padding-right: 44px; }

        .pw-toggle {
            position: absolute; right: 11px; top: 50%;
            transform: translateY(-50%);
            background: none; border: none;
            cursor: pointer; color: #94a3b8;
            padding: 4px; display: flex; align-items: center;
            transition: color 0.15s;
        }

        .pw-toggle:hover { color: #64748b; }

        .login-submit {
            width: 100%;
            padding: 13px 20px;
            border-radius: 10px; border: none;
            background: linear-gradient(135deg, #2563eb 0%, #dc2626 100%);
            color: white; cursor: pointer;
            font-weight: 800; font-family: inherit; font-size: 14px;
            box-shadow: 0 4px 20px rgba(37,99,235,0.28);
            transition: opacity 0.15s, transform 0.15s, box-shadow 0.15s;
            letter-spacing: 0.1px;
            display: flex; align-items: center; justify-content: center; gap: 8px;
        }

        .login-submit:hover:not(:disabled) {
            box-shadow: 0 6px 28px rgba(37,99,235,0.38);
            transform: translateY(-1px);
        }

        .login-submit:disabled { opacity: 0.7; cursor: wait; }

        .login-error {
            padding: 10px 14px;
            border-radius: 8px;
            background: #fef2f2; border: 1px solid #fecaca;
            font-size: 13px; color: #b91c1c;
            margin-bottom: 18px;
            display: flex; align-items: center; gap: 8px;
        }

        .login-divider {
            display: flex; align-items: center; gap: 12px;
            margin: 18px 0;
        }
        .login-divider-line {
            flex: 1; height: 1px; background: #e2e8f0;
        }
        .login-divider-text {
            font-size: 11px; color: #94a3b8; font-weight: 600;
        }

        .login-link {
            color: #2563eb; font-weight: 600; font-size: 13px;
            text-decoration: none;
            transition: color 0.15s;
        }
        .login-link:hover { color: #1d4ed8; text-decoration: underline; }

        .login-footer {
            position: absolute;
            bottom: 20px; left: 0; right: 0;
            text-align: center;
            font-size: 11.5px;
            color: rgba(147,197,253,0.35);
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50%       { transform: translateY(-12px); }
        }
        @keyframes pulseGlow {
            0%, 100% { opacity: 0.55; }
            50%       { opacity: 1; }
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
<div class="login-bg">
    <!-- Orbs -->
    <div class="orb orb-tr"></div>
    <div class="orb orb-bl"></div>
    <div class="orb orb-mid"></div>
    <div class="teal-streak"></div>
    <div class="grid-overlay"></div>

    <!-- Card -->
    <div class="login-card">
        <!-- Logo -->
        <div class="login-logo">
            <div class="login-logo-badge">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
                </svg>
            </div>
            <div class="login-logo-title">Finance Manager</div>
            <div class="login-logo-subtitle">Sign in to your account</div>
        </div>

        {{ $slot }}
    </div>

    <div class="login-footer">
        © {{ date('Y') }} Finance Manager &mdash; Personal Portfolio Tracker
    </div>
</div>

<script>
    // Password show/hide toggle
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.pw-toggle').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var input = document.querySelector(btn.dataset.target);
                if (!input) return;
                var isText = input.type === 'text';
                input.type = isText ? 'password' : 'text';
                btn.querySelector('.icon-eye').classList.toggle('hidden', !isText);
                btn.querySelector('.icon-eye-off').classList.toggle('hidden', isText);
            });
        });
    });
</script>
</body>
</html>
