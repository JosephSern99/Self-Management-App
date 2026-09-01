<x-app-layout>
    <x-slot name="header">Add New Fund</x-slot>

    <div style="max-width:540px;">

        {{-- Back link --}}
        <a href="{{ route('finance.home') }}" class="edic-btn edic-btn-secondary edic-btn-sm" style="margin-bottom:20px; display:inline-flex;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            Back to Finance Tracker
        </a>

        <div class="edic-card">
            <div style="margin-bottom:24px;">
                <h2 style="font-size:17px; font-weight:700; color:var(--edic-text-primary); margin:0 0 4px;">New Fund Entry</h2>
                <p style="font-size:13px; color:var(--edic-text-secondary); margin:0;">
                    Add a new asset to your portfolio. If the fund name already exists it will be restored and updated.
                </p>
            </div>

            {{-- Validation errors --}}
            @if ($errors->any())
                <div class="edic-alert edic-alert-error" style="margin-bottom:20px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <div>@foreach ($errors->all() as $error)<div>{{ $error }}</div>@endforeach</div>
                </div>
            @endif

            <form id="createFundForm" action="{{ route('finance.store') }}" method="POST" novalidate>
                @csrf

                {{-- Fund name --}}
                <div class="edic-form-group">
                    <label for="name" class="edic-label">Fund Name</label>
                    <input
                        id="name"
                        type="text"
                        name="name"
                        class="edic-input"
                        placeholder="e.g. EPF, ASB, Unit Trust, Stocks"
                        value="{{ old('name') }}"
                        required
                        autofocus
                    >
                    <div class="edic-input-hint">Use a unique name. Re-adding an existing name will restore & update it.</div>
                </div>

                {{-- Initial value --}}
                <div class="edic-form-group">
                    <label for="initial_value" class="edic-label">Initial Value (RM)</label>
                    <div style="position:relative;">
                        <span style="position:absolute; left:13px; top:50%; transform:translateY(-50%); font-size:14px; font-weight:600; color:var(--edic-text-secondary);">RM</span>
                        <input
                            id="initial_value"
                            type="text"
                            name="initial_value"
                            class="edic-input"
                            style="padding-left:40px;"
                            placeholder="0.00"
                            value="{{ old('initial_value') }}"
                            inputmode="decimal"
                            required
                        >
                    </div>
                    <div class="edic-input-hint">Commas accepted — e.g. <strong>10,000.50</strong> is valid.</div>
                </div>

                {{-- Hidden current_value (set to initial on submit) --}}
                <input type="hidden" id="current_value" name="current_value">

                {{-- Submit --}}
                <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:8px;">
                    <a href="{{ route('finance.home') }}" class="edic-btn edic-btn-secondary">Cancel</a>
                    <button type="submit" class="edic-btn edic-btn-primary" id="createBtn">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        Add Fund
                    </button>
                </div>
            </form>
        </div>
    </div>

    @push('scripts')
    <script>
    // Format input with commas on blur, accept raw numeric on focus
    var initialInput = document.getElementById('initial_value');

    function parseAmount(val) {
        return parseFloat(String(val).replace(/,/g, '').replace(/[^0-9.]/g, '')) || 0;
    }

    function formatAmount(val) {
        var n = parseAmount(val);
        if (!n) return '';
        return n.toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    initialInput.addEventListener('blur', function () {
        if (this.value.trim()) this.value = formatAmount(this.value);
    });

    initialInput.addEventListener('focus', function () {
        // Strip commas so user can edit the raw number
        this.value = String(parseAmount(this.value) || '');
        if (this.value === '0') this.value = '';
    });

    document.getElementById('createFundForm').addEventListener('submit', function (e) {
        e.preventDefault();

        var btn = document.getElementById('createBtn');
        var rawVal = parseAmount(initialInput.value);

        if (!document.getElementById('name').value.trim()) {
            edicToast('Please enter a fund name.', 'error');
            return;
        }
        if (!rawVal) {
            edicToast('Please enter a valid initial value.', 'error');
            initialInput.focus();
            return;
        }

        // Strip commas before sending
        initialInput.value = rawVal;
        document.getElementById('current_value').value = rawVal;

        btn.disabled = true;
        btn.innerHTML = '<span style="width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);border-top-color:white;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block;"></span> Adding…';

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
                edicToast(data.message || 'Fund added successfully.', 'success');
                setTimeout(function () { window.location.href = '/finance'; }, 800);
            } else {
                btn.disabled = false;
                btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Fund';
                edicToast(data.message || 'An error occurred.', 'error');
            }
        })
        .catch(function () {
            btn.disabled = false;
            btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Fund';
            edicToast('Network error. Please try again.', 'error');
        });
    });
    </script>
    @endpush
</x-app-layout>
