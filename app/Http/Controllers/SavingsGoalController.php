<?php

namespace App\Http\Controllers;

use App\Models\SavingsGoal;
use Illuminate\Http\Request;


class SavingsGoalController extends Controller
{
    //
    public function create(Request $request)
    {
        $validated = $request->validate([
            'goal_name' => 'required|string|max:255',
            'target_amount' => 'required|numeric',
            'deadline' => 'required|date',
        ]);

        SavingsGoal::create([
            'user_id' => auth()->id(),
            'goal_name' => $validated['goal_name'],
            'target_amount' => $validated['target_amount'],
            'saved_amount' => 0,
            'deadline' => $validated['deadline'],
        ]);

        return back()->with('success', 'Savings goal created!');
    }

    public function updateProgress($goalId, Request $request)
    {
        $validated = $request->validate(['amount' => 'required|numeric']);

        $goal = SavingsGoal::findOrFail($goalId);
        $goal->saved_amount += $validated['amount'];
        $goal->save();

        return back()->with('success', 'Progress updated!');
    }
}
