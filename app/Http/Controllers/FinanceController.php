<?php

namespace App\Http\Controllers;

use App\Models\FinancialEntity;
use App\Services\FinanceEntityService;
use Illuminate\Http\Request;
use DataTables;

class FinanceController extends Controller
{
    protected $financialEntityService;

    public function __construct(FinanceEntityService $financialEntityService)
    {
        $this->financialEntityService = $financialEntityService;
    }

    public function home(Request $request){
        if ($request->ajax()) {
            $entities = FinancialEntity::select(['id', 'name', 'initial_value', 'current_value'])->get();

            return DataTables::of($entities)

            ->addColumn('action', function($row) {
                $editUrl = route('finance.edit', ['id' => $row->id]); // Assuming you have a route named 'finance.edit'
                $deleteUrl = route('finance.delete', ['id' => $row->id]); // Assuming you have a route named 'finance.delete'

                // Placeholder action buttons without links
                return '
                        <a href="' . $editUrl . '" class="bg-dark text-white rounded hover:bg-blue-600 px-2 py-1">
                            Edit
                        </a>
                        <a href="javascript:void(0);" data-id="' . $row->id . '" class="bg-red-500 text-white rounded hover:bg-red-600 px-2 py-1 delete-button">
                            Delete
                        </a>';

            })
            ->rawColumns(['action'])
            ->make(true);
        }

        // Calculate the total portfolio value using the service
        $totalValue = $this->financialEntityService->calculateTotalPortfolioValue();

        // Pass data to the view
        return view('finance.home', compact('totalValue'));
    }

    public function create() {
        return view('finance.create');
    }

    public function store(Request $request)
    {
        // Step 1: Perform initial validation for the 'name' field
        $data = $request->validate([
            'name' => 'required|string|max:255',
        ]);


        // Step 2: Check if an existing record is found
        $existingRecord = FinancialEntity::withTrashed()->where('name', $data['name'])->first();

        // Step 3: Conditionally validate fields based on record existence
        if ($existingRecord) {
            // If the record exists, validate only 'current_value'
            $additionalData = $request->validate([
                'current_value' => 'required|numeric',
            ]);
        } else {
            $request['current_value'] =  $request['initial_value'];
            // If the record does not exist, validate both 'initial_value' and 'current_value'
            $additionalData = $request->validate([
                'initial_value' => 'required|numeric',
                'current_value' => 'required|numeric',
            ]);

            // // Set 'initial_value' equal to 'current_value' for new records
            // $additionalData['current_value'] = $additionalData['current_value'];
        }

        // Merge validated data
        $data = array_merge($data, $additionalData);

        // Step 4: Use updateOrCreate to update or create the record
        $updateData = ['current_value' => $data['current_value']];

        // Include 'initial_value' only if no existing record is found
        if (!isset($existingRecord)) {
            $updateData['initial_value'] = $data['initial_value'];
        }

        $entity = FinancialEntity::withTrashed()->updateOrCreate(
            ['name' => $data['name']],
            $updateData
        );



        if (!$entity->wasRecentlyCreated) {
            // Conditionally update 'current_value' only if an existing record is found
            $entity->update([
                'current_value' => $data['current_value']
            ]);
        }

        // If the existing record was soft-deleted, restore it and update
        if ($entity->trashed()) {
            $entity->restore();
            $entity->update(['current_value' => $data['current_value']]);
        }

        // Return a JSON response
        return response()->json([
            'success' => true,
            'message' => $entity->wasRecentlyCreated ? 'Entity created successfully.' : 'Entity updated successfully.',
            'entity' => $entity
        ]);
    }



    public function edit($id)
    {
        // Find the financial entity by its ID, including soft-deleted entities if needed
        $entity = FinancialEntity::withTrashed()->find($id);

        // If the entity doesn't exist, redirect or return an error
        if (!$entity) {
            return redirect()->route('finance.index')->with('error', 'Entity not found.');
        }

        // Pass the entity to the view
        return view('finance.edit', compact('entity'));
    }



    public function delete(Request $request, $id)
    {
        try {
            // Find the entity by ID
            $deleteEntity = FinancialEntity::findOrFail($id);

            // Perform soft delete or permanent delete as required
            $deleteEntity->delete(); // If using SoftDeletes, this will soft delete

            // Return a success response
            return response()->json([
                'success' => true,
                'message' => 'Item deleted successfully.'
            ]);
        } catch (ModelNotFoundException $e) {
            // Handle case where entity is not found
            return response()->json([
                'success' => false,
                'message' => 'Item not found.'
            ], 404);
        } catch (\Exception $e) {
            // Handle any other errors
            return response()->json([
                'success' => false,
                'message' => 'An error occurred while deleting the item.'
            ], 500);
        }
    }

}
