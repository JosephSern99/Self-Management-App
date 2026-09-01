<x-app-layout>
    <x-slot name="header">Finance Tracker</x-slot>

    {{-- Net worth + Add button row --}}
    <div style="display:grid; grid-template-columns:1fr auto; gap:20px; align-items:stretch; margin-bottom:24px;">
        <div class="edic-net-worth">
            <div class="edic-net-worth-label">Total Portfolio Net Worth</div>
            <div class="edic-net-worth-value">RM {{ number_format($totalValue, 2) }}</div>
            <div class="edic-net-worth-sub">Across all tracked funds</div>
        </div>
        <div style="display:flex; flex-direction:column; gap:10px; justify-content:center;">
            <a href="{{ route('finance.create') }}" class="edic-btn edic-btn-primary">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Add New Fund
            </a>
        </div>
    </div>

    {{-- Table card --}}
    <div class="edic-card" style="padding:0; overflow:hidden;">
        <div style="padding:18px 24px; border-bottom:1px solid var(--edic-border); display:flex; align-items:center; justify-content:space-between;">
            <div>
                <div style="font-size:15px; font-weight:700; color:var(--edic-text-primary);">All Funds</div>
                <div style="font-size:12px; color:var(--edic-text-muted); margin-top:2px;">Manage your financial portfolio</div>
            </div>
        </div>
        <div style="padding:20px 24px;">
            <table id="financialTable" style="width:100%;">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Fund Name</th>
                        <th>Initial Value (RM)</th>
                        <th>Current Value (RM)</th>
                        <th>Change</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    {{-- ── Edit Modal ─────────────────────────────────────────────────────── --}}
    <div id="editModal" style="position:fixed; inset:0; background:rgba(15,23,42,0.45); z-index:9000;">
        <div id="editModalDialog" style="background:white; border-radius:18px; padding:0; max-width:460px; width:92%; box-shadow:0 24px 64px rgba(0,0,0,0.16); animation:fadeInUp 0.22s ease; position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); user-select:none;">

            {{-- Drag handle / Header --}}
            <div id="editModalHandle" style="display:flex; align-items:flex-start; justify-content:space-between; padding:24px 28px 0; cursor:grab; border-radius:18px 18px 0 0;">
                <div>
                    <div style="display:flex; align-items:center; gap:7px; margin-bottom:3px;">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="9" cy="5" r="1" fill="#94a3b8"/><circle cx="9" cy="12" r="1" fill="#94a3b8"/><circle cx="9" cy="19" r="1" fill="#94a3b8"/><circle cx="15" cy="5" r="1" fill="#94a3b8"/><circle cx="15" cy="12" r="1" fill="#94a3b8"/><circle cx="15" cy="19" r="1" fill="#94a3b8"/></svg>
                        <div style="font-size:16px; font-weight:700; color:var(--edic-text-primary);">Update Fund</div>
                    </div>
                    <div id="editModalSubtitle" style="font-size:12.5px; color:var(--edic-text-secondary); padding-left:20px;"></div>
                </div>
                <button onclick="closeEditModal()" style="background:none; border:none; cursor:pointer; color:var(--edic-text-muted); padding:4px; display:flex; align-items:center; transition:color 0.15s; flex-shrink:0;" onmouseover="this.style.color='#0f172a'" onmouseout="this.style.color='var(--edic-text-muted)'">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <div style="padding:16px 28px 28px;">

            {{-- Read-only info strip --}}
            <div style="background:var(--edic-accent-light); border-radius:10px; padding:13px 16px; margin-bottom:22px; display:flex; gap:28px;">
                <div>
                    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--edic-accent-dark); margin-bottom:3px;">Fund</div>
                    <div id="editModalName" style="font-size:14px; font-weight:600; color:var(--edic-text-primary);"></div>
                </div>
                <div>
                    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--edic-accent-dark); margin-bottom:3px;">Initial Value</div>
                    <div id="editModalInitial" style="font-size:14px; font-weight:600; color:var(--edic-text-primary);"></div>
                </div>
            </div>

            <form id="editFundForm" novalidate>
                @csrf
                <input type="hidden" id="editFundName" name="name">

                {{-- Current value input --}}
                <div class="edic-form-group">
                    <label for="editCurrentValue" class="edic-label">Current Value (RM)</label>
                    <div style="position:relative;">
                        <span style="position:absolute; left:13px; top:50%; transform:translateY(-50%); font-size:14px; font-weight:600; color:var(--edic-text-secondary);">RM</span>
                        <input id="editCurrentValue" type="text" name="current_value" class="edic-input" style="padding-left:40px;" inputmode="decimal" placeholder="0.00">
                    </div>
                    <div class="edic-input-hint">Commas accepted — e.g. <strong>12,500.00</strong></div>
                </div>

                {{-- Live change preview --}}
                <div id="editChangePreview" style="background:#f8fafc; border:1px solid var(--edic-border); border-radius:10px; padding:12px 16px; margin-bottom:24px; display:flex; align-items:center; justify-content:space-between;">
                    <span style="font-size:12.5px; color:var(--edic-text-secondary); font-weight:500;">Change from initial:</span>
                    <span id="editChangeValue" style="font-size:13px; font-weight:700; color:var(--edic-text-muted);">—</span>
                </div>

                {{-- Actions --}}
                <div style="display:flex; gap:10px; justify-content:flex-end;">
                    <button type="button" class="edic-btn edic-btn-secondary" onclick="closeEditModal()">Cancel</button>
                    <button type="submit" class="edic-btn edic-btn-primary" id="editSaveBtn">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                        Save Changes
                    </button>
                </div>
            </form>
            </div>{{-- end inner padding div --}}
        </div>
    </div>

    {{-- ── Delete Modal ────────────────────────────────────────────────────── --}}
    <div id="deleteModal" style="display:none; position:fixed; inset:0; background:rgba(15,23,42,0.45); z-index:9000; align-items:center; justify-content:center; backdrop-filter:blur(2px);">
        <div style="background:white; border-radius:16px; padding:28px 32px; max-width:380px; width:92%; box-shadow:0 20px 60px rgba(0,0,0,0.15); animation:fadeInUp 0.2s ease;">
            <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
                <div style="width:40px; height:40px; background:#fef2f2; border-radius:10px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
                </div>
                <div>
                    <div style="font-size:15px; font-weight:700; color:#0f172a;">Delete Fund</div>
                    <div style="font-size:12.5px; color:#64748b; margin-top:2px;">This can be undone by re-adding the fund.</div>
                </div>
            </div>
            <p style="font-size:13.5px; color:#475569; margin:0 0 22px;">Are you sure you want to remove this fund from your portfolio?</p>
            <div style="display:flex; gap:10px; justify-content:flex-end;">
                <button class="edic-btn edic-btn-secondary" onclick="closeDeleteModal()">Cancel</button>
                <button class="edic-btn" id="deleteConfirmBtn"
                    style="background:#b91c1c; color:white; box-shadow:0 2px 8px rgba(185,28,28,0.25);"
                    onclick="confirmDelete()">Delete</button>
            </div>
        </div>
    </div>

    @push('scripts')
    @php $storeRoute = route('finance.store'); @endphp
    @php $createRoute = route('finance.create'); @endphp
    <script>
    var STORE_ROUTE  = '{{ $storeRoute }}';
    var CREATE_ROUTE = '{{ $createRoute }}';

    /* ── Helpers ──────────────────────────────────────────────────────────── */
    function parseAmt(val) {
        return parseFloat(String(val).replace(/,/g, '').replace(/[^0-9.]/g, '')) || 0;
    }
    function fmtAmt(val) {
        var n = parseAmt(val);
        return n ? n.toLocaleString('en-MY', {minimumFractionDigits:2, maximumFractionDigits:2}) : '';
    }

    /* ── Edit modal ───────────────────────────────────────────────────────── */
    var editInitialValue = 0;

    function openEditModal(id, name, initialVal, currentVal) {
        editInitialValue = parseFloat(initialVal);

        document.getElementById('editFundName').value    = name;
        document.getElementById('editModalName').textContent    = name;
        document.getElementById('editModalSubtitle').textContent = 'Updating current value';
        document.getElementById('editModalInitial').textContent  = 'RM ' + editInitialValue.toLocaleString('en-MY', {minimumFractionDigits:2, maximumFractionDigits:2});

        var cvInput = document.getElementById('editCurrentValue');
        cvInput.value = fmtAmt(currentVal);
        updateEditPreview();

        // Reset position to center on each open
        var dialog = document.getElementById('editModalDialog');
        dialog.style.top       = '50%';
        dialog.style.left      = '50%';
        dialog.style.transform = 'translate(-50%,-50%)';

        document.getElementById('editModal').classList.add('is-open');
        setTimeout(function(){ cvInput.focus(); cvInput.select(); }, 50);
    }

    function closeEditModal() {
        document.getElementById('editModal').classList.remove('is-open');
        var btn = document.getElementById('editSaveBtn');
        btn.disabled = false;
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Save Changes';
    }

    function updateEditPreview() {
        var current = parseAmt(document.getElementById('editCurrentValue').value);
        var diff    = current - editInitialValue;
        var pct     = editInitialValue > 0 ? (diff / editInitialValue) * 100 : 0;
        var sign    = diff >= 0 ? '+' : '';
        var color   = diff >= 0 ? '#047857' : '#b91c1c';
        var el      = document.getElementById('editChangeValue');
        if (current) {
            el.style.color  = color;
            el.textContent  = sign + 'RM ' + Math.abs(diff).toLocaleString('en-MY', {minimumFractionDigits:2, maximumFractionDigits:2})
                            + ' (' + sign + pct.toFixed(2) + '%)';
        } else {
            el.style.color  = '#94a3b8';
            el.textContent  = '—';
        }
    }

    var cvInput = document.getElementById('editCurrentValue');
    cvInput.addEventListener('input',  updateEditPreview);
    cvInput.addEventListener('blur',   function(){ if (this.value.trim()) this.value = fmtAmt(this.value); updateEditPreview(); });
    cvInput.addEventListener('focus',  function(){ var n = parseAmt(this.value); this.value = n ? String(n) : ''; });

    document.getElementById('editFundForm').addEventListener('submit', function(e) {
        e.preventDefault();
        var raw = parseAmt(cvInput.value);
        if (!raw) { edicToast('Please enter a valid current value.', 'error'); cvInput.focus(); return; }

        cvInput.value = raw;
        var btn = document.getElementById('editSaveBtn');
        btn.disabled = true;
        btn.innerHTML = '<span style="width:13px;height:13px;border:2px solid rgba(255,255,255,0.3);border-top-color:white;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block;"></span> Saving…';

        fetch(STORE_ROUTE, {
            method: 'POST',
            headers: { 'X-CSRF-TOKEN': window.CSRF_TOKEN, 'Accept': 'application/json' },
            body: new FormData(this)
        })
        .then(function(r){ return r.json(); })
        .then(function(data) {
            if (data.success) {
                closeEditModal();
                edicToast(data.message || 'Fund updated.', 'success');
                $('#financialTable').DataTable().ajax.reload(null, false);
            } else {
                btn.disabled = false;
                btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Save Changes';
                edicToast(data.message || 'An error occurred.', 'error');
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Save Changes';
            edicToast('Network error. Please try again.', 'error');
        });
    });

    document.getElementById('editModal').addEventListener('click', function(e) {
        if (e.target === this && !draggingActive) closeEditModal();
    });

    /* ── Drag-to-move ─────────────────────────────────────────────────────── */
    var draggingActive = false;
    (function () {
        var handle  = document.getElementById('editModalHandle');
        var dialog  = document.getElementById('editModalDialog');
        var dragging = false, ox = 0, oy = 0;

        function resetDrag() {
            if (!dragging) return;
            dragging = false;
            draggingActive = false;
            handle.style.cursor = 'grab';
        }

        handle.addEventListener('mousedown', function (e) {
            // Ignore clicks on the close button
            if (e.target.closest('button')) return;

            dragging = true;
            draggingActive = true;
            handle.style.cursor = 'grabbing';

            // On first drag, switch from centered transform to absolute px position
            var rect = dialog.getBoundingClientRect();
            dialog.style.top       = rect.top + 'px';
            dialog.style.left      = rect.left + 'px';
            dialog.style.transform = 'none';

            ox = e.clientX - rect.left;
            oy = e.clientY - rect.top;

            e.preventDefault();
        });

        document.addEventListener('mousemove', function (e) {
            if (!dragging) return;
            var ow = window.innerWidth;
            var oh = window.innerHeight;
            var dw = dialog.offsetWidth;
            var dh = dialog.offsetHeight;

            var newX = Math.min(Math.max(0, e.clientX - ox), ow - dw);
            var newY = Math.min(Math.max(0, e.clientY - oy), oh - dh);

            dialog.style.left = newX + 'px';
            dialog.style.top  = newY + 'px';
        });

        document.addEventListener('mouseup', resetDrag);
        // Safety net: mouse released outside browser window
        window.addEventListener('blur', resetDrag);
    })();

    /* ── Delete modal ─────────────────────────────────────────────────────── */
    var pendingDeleteId = null;

    function openDeleteModal(id) {
        pendingDeleteId = id;
        document.getElementById('deleteModal').style.display = 'flex';
    }
    function closeDeleteModal() {
        document.getElementById('deleteModal').style.display = 'none';
        pendingDeleteId = null;
        var btn = document.getElementById('deleteConfirmBtn');
        btn.disabled = false;
        btn.innerHTML = 'Delete';
    }
    function confirmDelete() {
        if (!pendingDeleteId) return;
        var btn = document.getElementById('deleteConfirmBtn');
        btn.disabled = true;
        btn.innerHTML = '<span style="width:13px;height:13px;border:2px solid rgba(255,255,255,0.3);border-top-color:white;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block;"></span>';

        fetch('/finance/delete/' + pendingDeleteId, {
            method: 'POST',
            headers: { 'X-CSRF-TOKEN': window.CSRF_TOKEN, 'Content-Type': 'application/json' }
        })
        .then(function(r){ return r.json(); })
        .then(function(data) {
            closeDeleteModal();
            if (data.success) {
                edicToast('Fund removed from portfolio.', 'success');
                $('#financialTable').DataTable().ajax.reload(null, false);
            } else {
                edicToast(data.message || 'Failed to delete.', 'error');
            }
        })
        .catch(function() {
            closeDeleteModal();
            edicToast('An error occurred. Please try again.', 'error');
        });
    }
    document.getElementById('deleteModal').addEventListener('click', function(e) {
        if (e.target === this) closeDeleteModal();
    });

    /* ── DataTable ────────────────────────────────────────────────────────── */
    window.addEventListener('load', function () {
        $.ajaxSetup({ headers: { 'X-CSRF-TOKEN': window.CSRF_TOKEN } });

        $('#financialTable').DataTable({
            processing:    true,
            serverSide:    true,
            paging:        false,
            info:          false,
            scrollY:       '285px',
            scrollCollapse: true,
            ajax: '{{ route("finance.home") }}',
            columns: [
                { data: 'id',            name: 'id', width: '48px' },
                { data: 'name',          name: 'name' },
                {
                    data: 'initial_value', name: 'initial_value', className: 'text-end',
                    render: function(d) { return 'RM ' + parseFloat(d).toLocaleString('en-MY', {minimumFractionDigits:2, maximumFractionDigits:2}); }
                },
                {
                    data: 'current_value', name: 'current_value', className: 'text-end',
                    render: function(d) { return 'RM ' + parseFloat(d).toLocaleString('en-MY', {minimumFractionDigits:2, maximumFractionDigits:2}); }
                },
                {
                    data: null, name: 'change', orderable: false, searchable: false,
                    render: function(row) {
                        var diff  = parseFloat(row.current_value) - parseFloat(row.initial_value);
                        var pct   = parseFloat(row.initial_value) > 0 ? (diff / parseFloat(row.initial_value)) * 100 : 0;
                        var color = diff >= 0 ? '#047857' : '#b91c1c';
                        var bg    = diff >= 0 ? '#ecfdf5' : '#fef2f2';
                        var sign  = diff >= 0 ? '+' : '';
                        return '<span style="background:' + bg + ';color:' + color + ';padding:3px 9px;border-radius:20px;font-size:12px;font-weight:600;">'
                             + sign + pct.toFixed(1) + '%</span>';
                    }
                },
                { data: 'action', name: 'action', orderable: false, searchable: false, className: 'text-center' }
            ],
            language: {
                processing: '<div style="display:flex;align-items:center;gap:8px;color:#64748b;font-size:13px;padding:8px 0;"><span style="width:16px;height:16px;border:2px solid #e2e8f0;border-top-color:#2563eb;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block;"></span> Loading…</div>',
                emptyTable: '<div style="text-align:center;padding:32px 0;color:#94a3b8;font-size:13.5px;">No funds yet. <a href="' + CREATE_ROUTE + '" style="color:#2563eb;font-weight:600;">Add your first fund →</a></div>',
                search: 'Search:',
                searchPlaceholder: 'Filter funds…'
            },
            dom: '<"d-flex justify-content-end mb-3"f>t',
            order: [[0, 'asc']]
        });
    });
    </script>
    @endpush
</x-app-layout>
