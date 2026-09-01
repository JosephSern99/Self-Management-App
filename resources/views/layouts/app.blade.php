<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>{{ config('app.name', 'Finance Manager') }}</title>

    {{-- Fonts --}}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

    {{-- DataTables CSS only (no Bootstrap 4 theme — we override styles ourselves) --}}
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">

    {{-- Bootstrap 5 CSS --}}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">

    {{-- App CSS (EDIC tokens + Tailwind) --}}
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body>
<div class="edic-layout">

    {{-- Sidebar --}}
    @include('layouts.navigation')

    {{-- Main --}}
    <div class="edic-main">

        {{-- Header --}}
        <header class="edic-header">
            <div class="edic-header-title">
                @isset($header){{ $header }}@else{{ config('app.name') }}@endisset
            </div>
            <div class="edic-header-right">
                {{-- Breadcrumb hint --}}
                <span style="font-size:12px; color:var(--edic-text-muted); font-weight:500;">
                    {{ Auth::user()->name }}
                </span>
                <div style="width:32px; height:32px; background:linear-gradient(135deg,#2563eb,#dc2626); border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; color:white;">
                    {{ strtoupper(substr(Auth::user()->name, 0, 1)) }}
                </div>
            </div>
        </header>

        {{-- Page content --}}
        <main class="edic-content">
            {{ $slot }}
        </main>

    </div>{{-- /.edic-main --}}
</div>{{-- /.edic-layout --}}

{{-- Toast container (populated via JS) --}}
<div id="edic-toast-area" style="position:fixed; bottom:24px; right:24px; z-index:9999; display:flex; flex-direction:column; gap:10px;"></div>

{{-- jQuery (required for DataTables) --}}
<script src="https://code.jquery.com/jquery-3.7.1.min.js" defer></script>
{{-- DataTables JS --}}
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js" defer></script>
{{-- Bootstrap 5 JS --}}
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js" defer></script>

<script>
    // CSRF token for all AJAX
    window.CSRF_TOKEN = '{{ csrf_token() }}';

    // Global toast helper
    function edicToast(message, type) {
        type = type || 'success';
        var area = document.getElementById('edic-toast-area');
        var t = document.createElement('div');
        t.className = 'edic-toast edic-toast-' + type;
        var icon = type === 'success'
            ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
            : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        t.innerHTML = icon + '<span style="color:#0f172a;">' + message + '</span>';
        area.appendChild(t);
        setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(function() { t.remove(); }, 350); }, 3500);
    }
</script>

@stack('scripts')
</body>
</html>
