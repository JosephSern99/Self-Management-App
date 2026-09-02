<x-app-layout>
    <x-slot name="header">
        <div class="flex items-center gap-4">
            <a href="{{ route('dashboard') }}" class="edic-btn edic-btn-secondary edic-btn-sm">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back
            </a>
            <h2 class="font-semibold text-xl text-gray-800 leading-tight">
                {{ __('Make Payment') }}
            </h2>
        </div>
    </x-slot>

    <div class="py-12">
        <div class="max-w-3xl mx-auto sm:px-6 lg:px-8">
            <div class="edic-card">
                <form id="payment-form">
                    <div class="edic-form-group">
                        <label for="amount" class="edic-label">Amount</label>
                        <input type="number" id="amount" name="amount" min="1" step="0.01" placeholder="Enter amount (min RM 1.00)" required class="edic-input">
                    </div>

                    <div class="edic-form-group">
                        <label for="card-element" class="edic-label">Card Details</label>
                        <div id="card-element" class="edic-input"></div>
                    </div>

                    <button type="submit" id="submit" class="edic-btn edic-btn-primary">Pay</button>
                </form>
            </div>
        </div>
    </div>

    <meta name="csrf-token" content="{{ csrf_token() }}">

    <script src="https://js.stripe.com/v3/"></script>
    <script>
        // Load Stripe
        const stripe = Stripe('{{ env("STRIPE_KEY") }}');
        const elements = stripe.elements();
        const cardElement = elements.create('card');
        cardElement.mount('#card-element');

        const form = document.getElementById('payment-form');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            // Get amount input value
            const amount = parseFloat(document.getElementById('amount').value);

            if (isNaN(amount) || amount < 1) {
                alert('The minimum payment amount is RM 1.00');
                return;
            }

            try {
                // Make a POST request to create a PaymentIntent
                const response = await fetch('/payment-intent', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]').getAttribute('content'), // Include CSRF token for Laravel
                    },
                    body: JSON.stringify({ amount: amount }), // Send the dynamic amount
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }

                const { clientSecret } = await response.json();

                // Confirm the card payment
                const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
                    payment_method: {
                        card: cardElement,
                    },
                });

                if (error) {
                    alert(`Payment failed: ${error.message}`);
                } else {
                    alert('Payment successful!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Something went wrong while processing your payment. Please try again.');
            }
        });
    </script>
</x-app-layout>