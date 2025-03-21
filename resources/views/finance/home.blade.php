<x-app-layout>
    <x-slot name="header">
        <div style="display: flex;
  justify-content: space-between;">
            <h2 class="font-semibold text-xl text-gray-800 dark:text-gray-200 leading-tight">
                {{ __('Finance Tracker') }}
            </h2>

            <h2 class="font-semibold text-xl text-gray-800 dark:text-gray-200 leading-tight">
                Total Net Worth: RM {{ number_format($totalValue, 2) }}
            </h2>
        </div>
    </x-slot>

    {{-- <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white dark:bg-gray-800 overflow-hidden shadow-sm sm:rounded-lg">
                <div class="p-6 text-gray-900 dark:text-gray-100">
                    {{ __("You're logged in!") }}
                </div>
            </div>
        </div>
    </div> --}}
    <div style="margin-bottom: 20px;"></div>
    <div class="flex">
        <div class="datatable-container max-w-7xl mx-auto p-4 bg-white rounded-lg shadow-md overflow-y-auto h-96">
            <!-- Set a fixed height -->
            <a href="{{ route('finance.create') }}" class="btn btn-primary">Add New Funds</a>
            <table id="financialTable" class="w-full table-auto border-collapse">
                <thead class="bg-dark text-white">
                    <tr>
                        <th class="px-4 py-2 border">ID</th>
                        <th class="px-4 py-2 border">Name</th>
                        <th class="px-4 py-2 border">Initial Value (RM)</th>
                        <th class="px-4 py-2 border">Current Value (RM)</th>
                        <th class="px-4 py-2 border">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- DataTables will dynamically populate the rows here -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Attach the event listener to the parent container (e.g., the table or a wrapper div)
        document.querySelector(".datatable-container").addEventListener("click", function(event) {
            // Check if the clicked element is a delete button
            if (event.target.classList.contains("delete-button")) {
                event.preventDefault(); // Prevent default link behavior
                const entityId = event.target.getAttribute("data-id");

                if (!confirm("Are you sure you want to delete this item?")) {
                    return; // Exit if the user cancels
                }

                // Proceed with the fetch request if the user confirmed
                fetch("/finance/delete/" + entityId, {
                        method: "POST",
                        headers: {
                            "X-CSRF-TOKEN": "{{ csrf_token() }}", // Use correct CSRF token syntax if in Blade
                            "Content-Type": "application/json"
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert("Item deleted successfully.");
                            location.reload(); // Reload the page or update the table
                        } else {
                            alert("Failed to delete the item.");
                        }
                    })
                    .catch(error => console.error("Error:", error));
            }
        });
    </script>
</x-app-layout>
