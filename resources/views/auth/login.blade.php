<x-guest-layout>
    {{-- Session status (e.g. after password reset) --}}
    @if (session('status'))
        <div class="login-error" style="background:#ecfdf5; border-color:#a7f3d0; color:#047857; margin-bottom:18px;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            {{ session('status') }}
        </div>
    @endif

    {{-- Validation errors --}}
    @if ($errors->any())
        <div class="login-error">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <div>
                @foreach ($errors->all() as $error)
                    <div>{{ $error }}</div>
                @endforeach
            </div>
        </div>
    @endif

    <form method="POST" action="{{ route('login') }}">
        @csrf

        {{-- Email --}}
        <div style="margin-bottom:16px;">
            <label for="email" class="login-label">Email address</label>
            <input
                id="email"
                type="email"
                name="email"
                value="{{ old('email') }}"
                class="login-input"
                placeholder="you@example.com"
                required
                autofocus
                autocomplete="username"
            >
        </div>

        {{-- Password --}}
        <div style="margin-bottom:22px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <label for="password" class="login-label" style="margin-bottom:0;">Password</label>
                @if (Route::has('password.request'))
                    <a href="{{ route('password.request') }}" class="login-link" style="font-size:12px;">Forgot password?</a>
                @endif
            </div>
            <div class="login-input-wrap">
                <input
                    id="password"
                    type="password"
                    name="password"
                    class="login-input has-toggle"
                    placeholder="Enter your password"
                    required
                    autocomplete="current-password"
                >
                <button type="button" class="pw-toggle" data-target="#password" tabindex="-1" aria-label="Toggle password visibility">
                    {{-- eye icon (shown when password hidden) --}}
                    <svg class="icon-eye" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                    </svg>
                    {{-- eye-off icon (shown when password visible) --}}
                    <svg class="icon-eye-off hidden" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                </button>
            </div>
        </div>

        {{-- Remember me --}}
        <div style="margin-bottom:20px; display:flex; align-items:center; gap:8px;">
            <input
                id="remember_me"
                type="checkbox"
                name="remember"
                style="width:15px; height:15px; accent-color:#2563eb; cursor:pointer;"
            >
            <label for="remember_me" style="font-size:13px; color:#64748b; font-weight:500; cursor:pointer; user-select:none;">
                Keep me signed in
            </label>
        </div>

        {{-- Submit --}}
        <button type="submit" class="login-submit" id="loginBtn">
            Sign In
        </button>
    </form>
</x-guest-layout>
