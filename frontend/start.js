document.getElementById('subForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btnId = e.submitter.id;

    let apiurl = "";
    if (btnId === "RG_button"){apiurl = '/api/create_group';}
    else if (btnId === "JG_button"){apiurl = '/api/join_group';}
    else if (btnId === "L_button"){apiurl = '/api/login';}
    try {
        const response = await fetch(apiurl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group_name: document.getElementById("GroupID").value,
                user_name: document.getElementById("UserID").value,
                password: document.getElementById("UserPass").value})
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem("current_group", data.group_name);
            localStorage.setItem("current_user", data.user_name);
            alert("Successfully Registered");
            window.location.href = "/compute.html";
        } else {alert("Error: " + (data.error || "Failed"));}
    } catch (err) {alert("Error");}
});
  