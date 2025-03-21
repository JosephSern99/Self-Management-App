<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class WebhookController extends Controller
{
    //
    public function handleWebhook(Request $request)
    {
        $payload = $request->all();

        // Example: Handle payment success event
        if ($payload['type'] === 'payment_intent.succeeded') {
            // Perform actions like updating your database
        }

        return response()->json(['status' => 'success']);
    }



}
