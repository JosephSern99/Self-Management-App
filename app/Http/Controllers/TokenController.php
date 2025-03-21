<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use App\Models\User;

class TokenController extends Controller
{
    public function createToken(Request $request)
    {
        // 1. Validate Request (Optional, but recommended)
        $request->validate([
            'email' => 'required|email',
            'password' => 'required',
        ]);

        // 2. Attempt to authenticate the user
        $credentials = $request->only('email', 'password');
        if (!Auth::attempt($credentials)) {
            return response()->json(['message' => 'Invalid credentials'], 401);
        }

        // 3. Get the authenticated user
        $user = User::where('email', $request->email)->first();

        // 4. Create a new token for the user
        $token = $user->createToken('MyToken')->plainTextToken;

        // 5. Return the token in the response
        return response()->json(['token' => $token]);
    }
}
