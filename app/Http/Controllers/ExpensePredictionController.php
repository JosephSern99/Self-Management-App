<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class ExpensePredictionController extends Controller
{
    public function predict(Request $request)
    {
        // can also use post request from user input to determine future expense
        // Input data for the Python script
        $expenseData = [
            ['month' => '2024-01', 'amount' => 5000],
            ['month' => '2024-02', 'amount' => 7000],
            ['month' => '2024-03', 'amount' => 3000],
        ];

        // Convert data to JSON for the Python script
        $inputJson = json_encode($expenseData);

        // Execute the Python script
        $command = 'python predict_expense.py';
        $process = proc_open(
            $command,
            [
                ['pipe', 'r'], // STDIN
                ['pipe', 'w'], // STDOUT
                ['pipe', 'w'], // STDERR
            ],
            $pipes
        );

        if (is_resource($process)) {
            fwrite($pipes[0], $inputJson);
            fclose($pipes[0]);

            // Get script output
            $output = stream_get_contents($pipes[1]);
            fclose($pipes[1]);

            // Get errors, if any
            $errors = stream_get_contents($pipes[2]);
            fclose($pipes[2]);

            proc_close($process);

            if ($errors) {
                return response()->json(['error' => $errors], 500);
            }

            // Decode Python script output
            $result = json_decode($output, true);
            return response()->json(['prediction next month is' => $result['prediction']]);
        }

        return response()->json(['error' => 'Failed to execute Python script'], 500);
    }

}
