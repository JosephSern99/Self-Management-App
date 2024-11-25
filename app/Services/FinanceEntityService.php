<?php

namespace App\Services;

use App\Models\FinancialEntity;

class FinanceEntityService
{
    public function calculateTotalPortfolioValue() {
        return FinancialEntity::sum('current_value');
    }
}
