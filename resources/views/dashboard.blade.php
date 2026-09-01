<x-app-layout>
    <x-slot name="header">Dashboard</x-slot>

    {{-- Welcome strip --}}
    <div class="edic-net-worth" style="margin-bottom:24px;">
        <div class="edic-net-worth-label">Welcome back</div>
        <div class="edic-net-worth-value" style="font-size:26px;">{{ Auth::user()->name }}</div>
        <div class="edic-net-worth-sub">{{ now()->format('l, d F Y') }}</div>
    </div>

    {{-- Quick nav cards --}}
    <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:16px; margin-bottom:24px;">

        <a href="{{ route('finance.home') }}" class="edic-stat-card" style="text-decoration:none; transition:transform 0.15s, box-shadow 0.15s;" onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='var(--edic-shadow-md)'" onmouseout="this.style.transform='';this.style.boxShadow=''">
            <div class="edic-stat-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
            </div>
            <div class="edic-stat-label">Finance Tracker</div>
            <div style="font-size:13.5px; color:var(--edic-text-secondary); font-weight:500; margin-top:2px;">Portfolio & fund management</div>
            <div style="margin-top:12px; font-size:12px; font-weight:600; color:var(--edic-accent); display:flex; align-items:center; gap:4px;">
                Open tracker
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
        </a>

        <a href="{{ route('finance.create') }}" class="edic-stat-card" style="text-decoration:none; transition:transform 0.15s, box-shadow 0.15s;" onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='var(--edic-shadow-md)'" onmouseout="this.style.transform='';this.style.boxShadow=''">
            <div class="edic-stat-icon" style="background:#f0fdf4;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </div>
            <div class="edic-stat-label">Add Fund</div>
            <div style="font-size:13.5px; color:var(--edic-text-secondary); font-weight:500; margin-top:2px;">Record a new asset</div>
            <div style="margin-top:12px; font-size:12px; font-weight:600; color:#16a34a; display:flex; align-items:center; gap:4px;">
                Add now
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
        </a>

        <a href="{{ route('payment.home') }}" class="edic-stat-card" style="text-decoration:none; transition:transform 0.15s, box-shadow 0.15s;" onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='var(--edic-shadow-md)'" onmouseout="this.style.transform='';this.style.boxShadow=''">
            <div class="edic-stat-icon" style="background:#eff6ff;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
            </div>
            <div class="edic-stat-label">Payments</div>
            <div style="font-size:13.5px; color:var(--edic-text-secondary); font-weight:500; margin-top:2px;">Stripe payment integration</div>
            <div style="margin-top:12px; font-size:12px; font-weight:600; color:#2563eb; display:flex; align-items:center; gap:4px;">
                Open
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
        </a>

        <a href="{{ route('profile.edit') }}" class="edic-stat-card" style="text-decoration:none; transition:transform 0.15s, box-shadow 0.15s;" onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='var(--edic-shadow-md)'" onmouseout="this.style.transform='';this.style.boxShadow=''">
            <div class="edic-stat-icon" style="background:#fdf4ff;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9333ea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div class="edic-stat-label">Profile</div>
            <div style="font-size:13.5px; color:var(--edic-text-secondary); font-weight:500; margin-top:2px;">Account settings</div>
            <div style="margin-top:12px; font-size:12px; font-weight:600; color:#9333ea; display:flex; align-items:center; gap:4px;">
                Edit profile
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
        </a>

    </div>
</x-app-layout>
