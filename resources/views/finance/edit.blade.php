<x-app-layout>
    <x-slot name="header">
        <!-- Scripts -->
        @vite(['resources/css/app.css', 'resources/js/app.js'])

    </x-slot>

    <div class="w-full sm:max-w-md mt-6 px-6 py-4 bg-white dark:bg-gray-800 shadow-md overflow-hidden sm:rounded-lg">
        <form id="financeForm" method="POST" action="{{ route('finance.store') }}">
            @csrf

            <!-- Name -->
            <div>
                <x-input-label for="name" :value="__('Name')" />
                <x-text-input id="name" class="block mt-1 w-full" type="text" name="name" value="{{ $entity->name }}" required autofocus autocomplete="name" />
                <x-input-error :messages="$errors->get('name')" class="mt-2" />
            </div>

            <!-- Current Value -->
            <div class="mt-4">
                <x-input-label for="currentValue" :value="__('Current Value')" />
                <x-text-input id="current_value" class="block mt-1 w-full" type="text" name="current_value" value="{{ $entity->current_value }}" required autocomplete="current_value" />
                <x-input-error :messages="$errors->get('currentValue')" class="mt-2" />
            </div>

            <div class="flex items-center justify-end mt-4">
                <a class="inline-flex items-center px-4 py-2 bg-gray-800 dark:bg-gray-200 border border-transparent rounded-md font-semibold text-xs text-white dark:text-gray-800 uppercase tracking-widest hover:bg-gray-700 dark:hover:bg-white focus:bg-gray-700 dark:focus:bg-white active:bg-gray-900 dark:active:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 transition ease-in-out duration-150" href="{{ route('finance.home') }}">
                    {{ __('Back') }}
                </a>

                <button type="submit" class="inline-flex items-center px-4 py-2 bg-gray-800 dark:bg-gray-200 border border-transparent rounded-md font-semibold text-xs text-white dark:text-gray-800 uppercase tracking-widest hover:bg-green-700 dark:hover:bg-green focus:bg-gray-700 dark:focus:bg-white active:bg-gray-900 dark:active:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800 transition ease-in-out duration-150">Update</button>
            </div>
        </form>
    </div>

    <script>
        document.getElementById('financeForm').addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission

            let formData = new FormData(this); // Capture form data
            let url = this.action; // Get the form action URL

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRF-TOKEN': '{{ csrf_token() }}',
                    'Accept': 'application/json'
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Display the success message as an alert
                if (data.success) {
                    alert(data.message); // Display the message returned from the controller
                } else {
                    alert('An error occurred: ' + (data.message || 'Please try again.'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
</script>

    </script>
</x-app-layout>
