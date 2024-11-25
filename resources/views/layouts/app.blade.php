<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="csrf-token" content="{{ csrf_token() }}">
        <title>{{ config('app.name', 'Laravel') }}</title>

        <!-- Fonts -->
        <link rel="preconnect" href="https://fonts.bunny.net">
        <link href="https://fonts.bunny.net/css?family=figtree:400,500,600&display=swap" rel="stylesheet" />
        <!-- jQuery -->
        <script src="https://code.jquery.com/jquery-3.7.1.js" integrity="sha256-eKhayi8LEQwp4NKxN+CfCh+3qOVUtJn3QNZ0TciWLP4=" crossorigin="anonymous"></script>
        <!-- DataTables CSS -->
        <link rel="stylesheet" href="https://cdn.datatables.net/1.10.25/css/dataTables.bootstrap4.min.css">
        <!-- DataTables JS -->
        <script src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.10.25/js/dataTables.bootstrap4.min.js"></script>

        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.min.js"></script>

        <!-- Scripts -->
        @vite(['resources/css/app.css', 'resources/js/app.js'])
    </head>
    <body class="font-sans antialiased">
        <div class="min-h-screen bg-gray-100 ">
            @include('layouts.navigation')

            <!-- Page Heading -->
            @if (isset($header))
                <header class="bg-dark dark:bg-gray-800 shadow">
                    <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                        {{ $header }}
                    </div>
                </header>
            @endif

            <!-- Page Content -->
            <main>
                {{ $slot }}
            </main>
        </div>
    </body>

    <script>
        $.ajaxSetup({
            headers: {
                'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
            }
        });


        $(document).ready(function() {
            console.log('Initializing DataTable');

            $(document).ready(function() {
                $.ajax({
                    url: "{{ route('finance.home') }}",
                    method: 'GET',
                    success: function(data) {
                        console.log("Data received:", data);
                    },
                    error: function(xhr) {
                        console.log("AJAX Error:", xhr);
                    }
                });
            });

            $('#financialTable').DataTable({
                processing: true,
                serverSide: true,
                ajax: "{{ route('finance.home') }}",
                columns: [
                    { data: 'id', name: 'id', className: 'text-center'  },
                    { data: 'name', name: 'name' },
                    { data: 'initial_value', name: 'initial_value', className: 'text-center'  },
                    { data: 'current_value', name: 'current_value', className: 'text-center'  },
                    { data: 'action', name: 'action', orderable: false, searchable: false  }
                ],
                dom: 'Bfrtip',  // Adding buttons for export options (optional)
                buttons: ['copy', 'excel', 'pdf']  // Optional: Allows exporting to Excel, PDF, etc.
            });


        });

    </script>
</html>
