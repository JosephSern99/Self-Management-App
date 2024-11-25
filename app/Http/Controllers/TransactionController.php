<?php

namespace App\Http\Controllers;

use App\Models\Transaction;
use Illuminate\Http\Request;

class TransactionController extends Controller
{
    public function store(Request $request)
    {
        $validated = $request->validate([
            'category' => 'required|string',
            'amount' => 'required|numeric',
            'type' => 'required|in:income,expense',
            'transaction_date' => 'required|date',
        ]);


        $categories = [
            'groceries' => ['supermarket', 'grocery', 'food'],
            'utilities' => ['electricity', 'water', 'internet', 'phone'],
            'transport' => ['fuel', 'uber', 'taxi', 'bus'],
        ];

        $inputDescription = strtolower($request->input('description', ''));
        $category = 'others';

        foreach ($categories as $key => $keywords) {
            foreach ($keywords as $keyword) {
                if (strpos($inputDescription, $keyword) !== false) {
                    $category = $key;
                    break 2;
                }
            }
        }

        Transaction::create([
            'user_id' => auth()->id(),
            'category' => $category,
            'amount' => $validated['amount'],
            'type' => $validated['type'],
            'transaction_date' => $validated['transaction_date'],
        ]);

        return back()->with('success', 'Transaction recorded successfully!');
    }
}
