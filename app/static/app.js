document.getElementById('scheduleForm').addEventListener('submit', submitForm);

async function submitForm(event) {
    event.preventDefault();
    const n_teams = document.getElementById('n_teams').value;
    const n_matches_per_team = document.getElementById('n_matches_per_team').value;
    const n_rooms = document.getElementById('n_rooms').value;
    const n_time_slots = document.getElementById('n_time_slots').value;

    // Show the loading spinner
    document.getElementById('spinner').style.display = 'block';

    try {
        console.log("Sending request...");

        const response = await fetch('/generate-schedule/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                n_teams: parseInt(n_teams),
                n_matches_per_team: parseInt(n_matches_per_team),
                n_rooms: parseInt(n_rooms),
                n_time_slots: parseInt(n_time_slots)
            })
        });

        console.log("Response received...");

        // Hide the loading spinner
        document.getElementById('spinner').style.display = 'none';

        // Clear the table and error message regardless of success or failure
        const resultTable = document.getElementById('resultTable').querySelector('tbody');
        resultTable.innerHTML = '';  // Clear table
        document.getElementById('error-message').textContent = '';  // Clear error message

        // Check for a successful response
        if (response.ok) {
            const data = await response.json();
            console.log("Data received: ", data);
            displaySchedule(data.schedule, data.constraints_relaxed); // Display the new schedule
        } else {
            const errorData = await response.json();
            console.log("Error response received: ", errorData);
            displayError(errorData.detail);  // Display the error message
        }
    } catch (error) {
        // Hide the loading spinner
        document.getElementById('spinner').style.display = 'none';

        console.log("Error occurred: ", error);

        // Clear the table and display error message
        document.getElementById('resultTable').querySelector('tbody').innerHTML = '';
        displayError('An unexpected error occurred. Please try again.');
    }
}

function displayError(message) {
    console.log("Displaying error: ", message);
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';  // Show the error message
}

function displaySchedule(schedule, constraints_relaxed) {
    console.log("Displaying schedule...");
    const resultTable = document.getElementById('resultTable').querySelector('tbody');

    // Clear the existing table rows
    resultTable.innerHTML = '';

    schedule.forEach(row => {
        const tr = document.createElement('tr');

        // TimeSlot
        const timeSlotTd = document.createElement('td');
        timeSlotTd.textContent = row.TimeSlot;
        tr.appendChild(timeSlotTd);

        // Room
        const roomTd = document.createElement('td');
        roomTd.textContent = row.Room;
        tr.appendChild(roomTd);

        // Matchup
        const matchupTd = document.createElement('td');

        if (row.Matchup && row.Matchup.teams) {
            matchupTd.textContent = row.Matchup.teams.join(", ");
        } else {
            matchupTd.textContent = "N/A";
        }
        tr.appendChild(matchupTd);

        resultTable.appendChild(tr);
    });

    // If any constraints were relaxed, display the information
    if (constraints_relaxed.length > 0) {
        const relaxedMessage = `The following constraints were relaxed: ${constraints_relaxed.join(', ')}.`;
        displayError(relaxedMessage);
    } else {
        // Hide error message if schedule is successfully loaded
        document.getElementById('error-message').style.display = 'none';
    }
}
