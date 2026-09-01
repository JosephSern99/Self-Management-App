<x-app-layout>
    <x-slot name="header">Update Fund</x-slot>

    <div style="max-width:540px;">

        {{-- Back link --}}
        <a href="{{ route('finance.home') }}" class="edic-btn edic-btn-secondary edic-btn-sm" style="margin-bottom:20px; display:inline-flex;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            Back to Finance Tracker
        </a>

        <div class="edic-card">
            <div style="margin-bottom:24px;">
                <h2 style="font-size:17px; font-weight:700; color:var(--edic-text-primary); margin:0 0 4px;">Update Fund</h2>
                <p style="font-size:13px; color:var(--edic-text-secondary); margin:0;">
                    Update the current value of <strong>{{ $entity->name }}</strong>.
                </p>
            </div>

            {{-- Read-only summary strip --}}
            <div style="background:var(--edic-accent-light); border-radius:10px; padding:14px 16px; margin-bottom:24px; display:flex; gap:24px;">
                <div>
                    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--edic-accent-dark); margin-bottom:3px;">Fund Name</div>
                    <div style="font-size:14px; font-weight:600; color:var(--edic-text-primary);">{{ $entity->name }}</div>
                </div>
                <div>
                    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--edic-accent-dark); margin-bottom:3px;">Initial Value</div>
                    <div style="font-size:14px; font-weight:600; color:var(--edic-text-primary);">RM {{ number_format($entity->initial_value, 2) }}</div>
                </div>
            </div>

            <form id="editFundForm" method="POST" action="{{ route('finance.store') }}" novalidate>
                @csrf
                <input type="hidden" name="name" value="{{ $entity->name }}">

                {{-- Current value --}}
                <div class="edic-form-group">
                    <label for="current_value" class="edic-label">Current Value (RM)</label>
                    <div style="position:relative;">
                        <span style="position:absolute; left:13px; top:50%; transform:translateY(-50%); font-size:14px; font-weight:600; color:var(--edic-text-secondary);">RM</span>
                        <input
                            id="current_value"
                            type="text"
                            name="current_value"
                            class="edic-input"
                            style="padding-left:40px;"
                            value="{{ number_format($entity->current_value, 2) }}"
                            inputmode="decimal"
                            required
                        >
                    </div>
                    <div class="edic-input-hint">Commas accepted — e.g. <strong>12,500.00</strong> is valid.</div>
                </div>

                {{-- Change preview (live) --}}
                <div id="changePreview" style="background:#f8fafc; border:1px solid var(--edic-border); border-radius:10px; padding:13px 16px; margin-bottom:22px; display:flex; align-items:center; justify-content:space-between;">
                    <span style="font-size:12.5px; color:var(--edic-text-secondary); font-weight:500;">Portfolio change from initial:</span>
                    <span id="changeValue" style="font-size:13.5px; font-weight:700; color:var(--edic-text-primary);">—</span>
                </div>

                {{-- Submit --}}
                <div style="display:flex; gap:10px; justify-content:flex-end;">
                    <a href="{{ route('finance.home') }}" class="edic-btn edic-btn-secondary">Cancel</a>
                    <button type="submit" class="edic-btn edic-btn-primary" id="updateBtn">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                        Update Fund
                    </button>
                </div>
            </form>
        </div>
    </div>

    @push('scripts')
    <script>
    var initialValue = {{ (float) $entity->initial_value }};
    var cvInput = document.getElementById('current_value');

    function parseAmount(val) {
        return parseFloat(String(val).replace(/,/g, '').replace(/[^0-9.]/g, '')) || 0;
    }

    function formatAmount(val) {
        var n = parseAmount(val);
        if (!n) return '';
        return n.toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function updateChangePreview() {
        var current = parseAmount(cvInput.value);
        var diff    = current - initialValue;
        var pct     = initialValue > 0 ? (diff / initialValue) * 100 : 0;
        var sign    = diff >= 0 ? '+' : '';
        var color   = diff >= 0 ? '#047857' : '#b91c1c';
        var el      = document.getElementById('changeValue');
        if (current) {
            el.style.color = color;
            el.textContent = sign + 'RM ' + Math.abs(diff).toLocaleString('en-MY', {minimumFractionDigits:2, maximumFractionDigits:2})
                           + ' (' + sign + pct.toFixed(2) + '%)';
        } else {
            el.style.color = '#94a3b8';
            el.textContent = '—';
        }
    }

    cvInput.addEventListener('input', updateChangePreview);

    cvInput.addEventListener('blur', function () {
        if (this.value.trim()) this.value = formatAmount(this.value);
        updateChangePreview();
    });

    cvInput.addEventListener('focus', function () {
        this.value = String(parseAmount(this.value) || '');
        if (this.value === '0') this.value = '';
    });

    // Initial preview
    updateChangePreview();

    document.getElementById('editFundForm').addEventListener('submit', function (e) {
        e.preventDefault();

        var rawVal = parseAmount(cvInput.value);
        if (!rawVal) {
            edicToast('Please enter a valid current value.', 'error');
            cvInput.focus();
            return;
        }

        // Strip commas before sending
        cvInput.value = rawVal;

        var btn = document.getElementById('updateBtn');
        btn.disabled = true;
        btn.innerHTML = '<span style="width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);border-top-color:white;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block;"></span> Updating…';

        var formData = new FormData(this);

        fetch(this.action, {
            method: 'POST',
            headers: {
                'X-CSRF-TOKEN': window.CSRF_TOKEN,
                'Accept': 'application/json'
            },
            body: formData
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                edicToast(data.message || 'Fund updated successfully.', 'success');
                setTimeout(function () { window.location.href = '/finance'; }, 800);
            } else {
                btn.disabled = false;
                btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Update Fund';
                edicToast(data.message || 'An error occurred.', 'error');
            }
        })
        .catch(function () {
            btn.disabled = false;
            btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Update Fund';
            edicToast('Network error. Please try again.', 'error');
        });
    });
    </script>
    @endpush
</x-app-layout>
