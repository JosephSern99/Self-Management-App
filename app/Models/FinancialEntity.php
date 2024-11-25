<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class FinancialEntity extends Model
{
    use SoftDeletes;
    use HasFactory;


    protected $fillable = ['name','initial_value','current_value'];
}
