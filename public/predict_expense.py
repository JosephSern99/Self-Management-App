import sys
import json
import pandas as pd
import joblib

# Load the pre-trained model
model = joblib.load('expense_model.pkl')

# Function to predict expense
def predict_expense(data):
    # Convert the input data into the format the model expects
    df = pd.DataFrame(data)

    # Assuming 'month' is the feature used for prediction
    df['month'] = pd.to_datetime(df['month'])
    df['month'] = df['month'].apply(lambda x: x.month)  # Convert to numeric month

    # Make predictions using the loaded model
    predicted = model.predict(df[['month']])  # Predict using the model

    return predicted.mean()  # Example: return the average predicted expense

def main():
    # Read input from Laravel (via shell exec)
    input_data = json.loads(sys.stdin.read())

    # Predict expenses
    predicted = predict_expense(input_data)

    # Output the prediction in JSON format
    output = {'prediction': "RM" + str(round(predicted, 2))}
    print(json.dumps(output))

if __name__ == "__main__":
    main()
