<?php

use App\Http\Controllers\ProfileController;
use App\Http\Controllers\FinanceController;
use App\Http\Controllers\TransactionController;
use App\Http\Controllers\ExpensePredictionController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
|
| Here is where you can register web routes for your application. These
| routes are loaded by the RouteServiceProvider and all of them will
| be assigned to the "web" middleware group. Make something great!
|
*/

Route::get('/', function () {
    return view('welcome');
});

Route::get('/dashboard', function () {
    return view('dashboard');
})->middleware(['auth', 'verified'])->name('dashboard');

Route::middleware('auth')->group(function () {
    Route::get('/profile', [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile', [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');

    Route::get('/finance', [FinanceController::class, 'home'])->name('finance.home');
    Route::get('/finance/create', [FinanceController::class, 'create'])->name('finance.create');
    Route::post('/finance/store', [FinanceController::class, 'store'])->name('finance.store');
    Route::get('/finance/edit/{id}', [FinanceController::class, 'edit'])->name('finance.edit');
    Route::post('/finance/delete/{id}', [FinanceController::class, 'delete'])->name('finance.delete');

    Route::post('/transactions/store', [TransactionController::class, 'store'])->name('transactions.store');


    Route::get('/predict-expense', [ExpensePredictionController::class, 'predict']);

    // demo purpose
    // Route::get('/holiday', [HolidayPlannerController::class, 'index'])->name('planner.home');
});

require __DIR__.'/auth.php';
