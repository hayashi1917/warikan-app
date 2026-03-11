document.getElementById('subForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btnId = e.submitter.id;
    const GroupID = document.getElementById("GroupID").value;
    const UserID = document.getElementById("UserID").value;
    const UserPass = document.getElementById("UserPass").value;

    if (!GroupID) { alert("Valid GroupID is required."); return }
    if (!UserID) { alert("Valid UserID is required."); return }
    if (!UserPass) { alert("Valid UserPass is required."); return }


    let apiUrl = "";
    let okText = "";
    if (btnId === "RG_button") {
        apiUrl = '/register/register_group';
        okText = "Group registered successfully!";
    }
    else if (btnId === "JG_button") {
        apiUrl = '/register/join_group';
        okText = "Successfully joined the group!";

    }
    else if (btnId === "L_button") {
        apiUrl = '/register/login';
        okText = "Login successful!";
    }

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group_name: GroupID,
                user_name: UserID,
                password: UserPass
            })
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem("current_group", data.group_name);
            localStorage.setItem("current_user", data.user_name);
            alert(okText);
            window.location.href = data.redirect_url || "/payment";
        } else { alert("Error: " + data.error); }
    } catch (err) { alert("Network error"); }
});
