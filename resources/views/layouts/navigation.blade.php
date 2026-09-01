<aside class="edic-sidebar" id="edicSidebar">

    {{-- Logo --}}
    <div class="edic-sidebar-logo">
        <a href="{{ route('dashboard') }}" class="edic-sidebar-logo-link">
            <span class="edic-sidebar-logo-badge">FM</span>
            <div>
                <div class="edic-sidebar-logo-text">Finance Manager</div>
                <div class="edic-sidebar-logo-sub">Personal Portfolio</div>
            </div>
        </a>
    </div>

    {{-- Nav --}}
    <nav class="edic-sidebar-nav">

        <div class="edic-sidebar-label">Main</div>

        <a href="{{ route('dashboard') }}"
           class="edic-nav-link {{ request()->routeIs('dashboard') ? 'active' : '' }}">
            <svg class="edic-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
            Dashboard
        </a>

        <a href="{{ route('finance.home') }}"
           class="edic-nav-link {{ request()->routeIs('finance.*') ? 'active' : '' }}">
            <svg class="edic-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
            </svg>
            Finance Tracker
        </a>

        <span class="edic-nav-link" style="opacity:0.35; cursor:not-allowed; pointer-events:none;">
            <svg class="edic-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>
            </svg>
            Payments
            <span style="margin-left:auto; font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">Soon</span>
        </span>

        <div class="edic-sidebar-label" style="margin-top:8px;">Account</div>

        <a href="{{ route('profile.edit') }}"
           class="edic-nav-link {{ request()->routeIs('profile.*') ? 'active' : '' }}">
            <svg class="edic-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
            </svg>
            Profile
        </a>

    </nav>

    {{-- User + Sign out --}}
    <div class="edic-sidebar-footer">
        <div class="edic-user-block">
            <div class="edic-user-avatar" style="background:linear-gradient(135deg,#2563eb,#dc2626);">{{ strtoupper(substr(Auth::user()->name, 0, 1)) }}</div>
            <div style="min-width:0; flex:1;">
                <div class="edic-user-name">{{ Auth::user()->name }}</div>
                <div class="edic-user-email">{{ Auth::user()->email }}</div>
            </div>
        </div>

        <form method="POST" action="{{ route('logout') }}">
            @csrf
            <button type="submit" class="edic-nav-link" style="margin-top:2px; color:rgba(148,163,184,0.6);">
                <svg class="edic-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                Sign Out
            </button>
        </form>
    </div>

</aside>
