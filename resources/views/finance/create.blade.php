<x-app-layout>
    <x-slot name="header">
      @vite(['resources/css/app.css', 'resources/js/app.js'])
        <h2 class="font-semibold text-xl text-gray-800 dark:text-gray-200 leading-tight">
            {{ __('Finance New Model') }}
        </h2>
    </x-slot>


    <div class="w-full sm:max-w-md mt-6 px-6 py-4 bg-white dark:bg-gray-800 shadow-md overflow-hidden sm:rounded-lg mx-auto">
        <form id="financialEntityForm" action="{{ route('finance.store') }}" method="POST">
            @csrf
            <div>
                <x-input-label for="name" :value="__('Finance Item')" />
                <x-text-input id="name" class="block mt-1 w-full" type="text" name="name" required autofocus autocomplete="name" />
                <x-input-error :messages="$errors->get('name')" class="mt-2" />
            </div>

            <div class="mt-4">
                <x-input-label for="initialValue" :value="__('Initial Value')" />
                <x-text-input id="initial_value" class="block mt-1 w-full" type="text" name="initial_value" required autocomplete="initial_value" />
                <x-input-error :messages="$errors->get('initialValue')" class="mt-2" />
            </div>

            <x-text-input id="current_value" class="block mt-1 w-full" type="hidden" name="current_value" required autocomplete="current_value" />

            <div class="flex items-center justify-end mt-4">
                <button type="submit" class="inline-flex items-center px-4 py-2 bg-gray-800 dark:bg-gray-200 border border-transparent rounded-md font-semibold text-xs text-white dark:text-gray-800 uppercase tracking-widest hover:bg-green-700 dark:hover:bg-green focus:bg-gray-700 dark:focus:bg-white active:bg-gray-900 dark:active:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-green-800 transition ease-in-out duration-150">Create</button>
            </div>
        </form>
    </div>

     <div class="loader hidden" id="loader"></div>



    <style>
        .loader {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            border: 5px solid #ccc;
            border-top-color: #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            z-index: 9999;
        }
        .loader.hidden {
            display: none;
        }
        @keyframes spin {
            0% {
                transform: rotate(0deg);
            }
            100% {
                transform: rotate(360deg);
            }
        }
    </style>

    <script>
        // Function to show the loader
        const showLoader = () => {
            document.getElementById('loader').classList.remove('hidden');
        };

        // Function to hide the loader
        const hideLoader = () => {
            document.getElementById('loader').classList.add('hidden');
        };


        document.getElementById('financialEntityForm').addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission

            showLoader();

            let formData = new FormData(this); // Capture form data
            let url = this.action; // Get the form action URL

            const initialValue = document.getElementById('initial_value').value;

            // Set the initial_value to be the same as current_value
            document.getElementById('current_value').value = initialValue;

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
                     hideLoader();
                    alert(data.message); // Display the message returned from the controller
                    location.href = '/finance'
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


</x-app-layout>
