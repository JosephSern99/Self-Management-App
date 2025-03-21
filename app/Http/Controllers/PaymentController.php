<?php

namespace App\Http\Controllers;

use Illuminate\Contracts\View\View;
use Illuminate\Http\Request;
use Stripe\StripeClient;

class PaymentController extends Controller
{
    //
    public function createPaymentIntent(Request $request)
    {
        if (!$request->isMethod('post')) {
            abort(405, 'Method Not Allowed');
        }


        $request->validate([
            'amount' => 'required|numeric|min:1',
        ]);

        $stripe = new \Stripe\StripeClient(env('STRIPE_SECRET'));

        $amountInCents = $request->amount * 100;

        $paymentIntent = $stripe->paymentIntents->create([
            'amount' => $amountInCents,
            'currency' => 'myr',
            'payment_method_types' => ['card'],
        ]);

        return response()->json(['clientSecret' => $paymentIntent->client_secret]);
    }


    public function home() : View
    {
        return view('payment.home');
    }
}
