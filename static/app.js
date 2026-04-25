/* app.js - Frontend logic for MediBridge */

let currentPage = 1;
const PAGE_LIMIT = 10;
let currentSearchData = {};
let isLoading = false;

async function searchMedicines(isNewSearch = true) {
  if (isLoading) return;

  const spinner = document.getElementById('loading-spinner');
  const searchBtn = document.querySelector('.search-btn');

  if (isNewSearch) {
    currentPage = 1;
    
    // Clear previous results safely if table exists
    const tableContainer = document.getElementById('results-table');
    if (tableContainer) tableContainer.innerHTML = '';
    
    const oldBtnContainer = document.getElementById('load-more-container');
    if (oldBtnContainer) oldBtnContainer.innerHTML = '';
    
    // Hide results container
    const resContainer = document.getElementById('results-container');
    if (resContainer) resContainer.style.display = 'none';

    // Check if on search page
    const hospInput = document.getElementById('hospital-id');
    const medInput = document.getElementById('medicine-code');
    const sortInput = document.getElementById('sort-by');
    
    if (!hospInput || !medInput || !sortInput) return;

    currentSearchData = {
      hospitalId: hospInput.value,
      medicineCode: medInput.value,
      sortBy: sortInput.value
    };
  } else {
    currentPage += 1;
  }

  // Validation
  if (!currentSearchData.hospitalId) {
    alert('Please enter your Hospital ID');
    return;
  }

  if (!currentSearchData.medicineCode) {
    alert('Please select a medicine');
    return;
  }

  try {
    isLoading = true;
    if (spinner) spinner.style.display = 'block';
    if (searchBtn && isNewSearch) searchBtn.disabled = true;

    // Call backend API with pagination parameters
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        hospital_id: parseInt(currentSearchData.hospitalId),
        item_code: currentSearchData.medicineCode,
        sort_by: currentSearchData.sortBy,
        page: currentPage,
        limit: PAGE_LIMIT
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }

    // Set isLoading to false before displayResults so UI reflects non-loading state
    isLoading = false; 
    
    // Display paginated results
    displayResults(data.results, isNewSearch, data.total);

  } catch (error) {
    console.error('Error:', error);
    alert('Error searching medicines. Please check console.');
    isLoading = false; // Ensure it's reset on error
  } finally {
    if (spinner) spinner.style.display = 'none';
    if (searchBtn && isNewSearch) searchBtn.disabled = false;
  }
}

function displayResults(results, isNewSearch, totalAvailable) {
  const container = document.getElementById('results-container');
  const tableContainer = document.getElementById('results-table');
  
  if (!container || !tableContainer) return; // Prevent errors if not on search page
  
  if (isNewSearch && (!results || results.length === 0)) {
    tableContainer.innerHTML = '<p style="color: #666; font-style: italic;">No hospitals found with this medicine in your region.</p>';
    container.style.display = 'block';
    const oldBtnContainer = document.getElementById('load-more-container');
    if (oldBtnContainer) oldBtnContainer.remove();
    return;
  }

  let html = '';
  
  if (isNewSearch) {
    html += `
      <table id="data-table">
        <thead>
          <tr>
            <th>Hospital Name</th>
            <th>City</th>
            <th>State</th>
            <th>Quantity</th>
            <th>Price (Rs)</th>
            <th>Delivery Time (hrs)</th>
            <th>Distance (km)</th>
          </tr>
        </thead>
        <tbody id="table-body">
    `;
  }

  results.forEach(result => {
    const delivery = result.delivery_time !== null 
      ? result.delivery_time.toFixed(2) 
      : 'Computing...';
    
    html += `
      <tr>
        <td>${result.hospital.name}</td>
        <td>${result.hospital.city}</td>
        <td>${result.hospital.state}</td>
        <td>${result.quantity}</td>
        <td>Rs ${result.price.toFixed(2)}</td>
        <td>${delivery}</td>
        <td>${result.distance.toFixed(2)}</td>
      </tr>
    `;
  });

  if (isNewSearch) {
    html += `
        </tbody>
      </table>
    `;
    tableContainer.innerHTML = html;
    
    // Add "Load More" button container if not exists
    if (!document.getElementById('load-more-container')) {
      const btnContainer = document.createElement('div');
      btnContainer.id = 'load-more-container';
      btnContainer.style.textAlign = 'center';
      btnContainer.style.marginTop = '20px';
      container.appendChild(btnContainer);
    }
  } else {
    // Append to existing table dynamically without destroying DOM
    const tbody = document.getElementById('table-body');
    if (tbody) {
      tbody.insertAdjacentHTML('beforeend', html);
    }
  }

  container.style.display = 'block';

  // Manage Load More button logic
  const btnContainer = document.getElementById('load-more-container');
  if (btnContainer) {
    btnContainer.innerHTML = ''; // Clear old button
    
    // Calculate total rendered results so far
    let currentTotalLoaded = currentPage * PAGE_LIMIT;
    
    // Fix boundary limit
    currentTotalLoaded = Math.min(currentTotalLoaded, totalAvailable);
    
    if (currentTotalLoaded < totalAvailable) {
      const loadMoreBtn = document.createElement('button');
      loadMoreBtn.id = 'load-more-btn';
      loadMoreBtn.className = 'btn search-btn'; // reuse existing styling
      loadMoreBtn.style.marginTop = '15px';
      
      const loadBtnText = `Load More (Showing ${currentTotalLoaded} of ${totalAvailable})`;
      loadMoreBtn.textContent = loadBtnText;
      
      loadMoreBtn.onclick = () => {
        loadMoreBtn.textContent = 'Loading...';
        loadMoreBtn.disabled = true;
        searchMedicines(false);
      };
      btnContainer.appendChild(loadMoreBtn);
    } else if (totalAvailable > 0) {
      const endMsg = document.createElement('p');
      endMsg.style.color = '#666';
      endMsg.style.marginTop = '15px';
      endMsg.style.fontWeight = 'bold';
      endMsg.textContent = `No more results. All ${totalAvailable} loaded.`;
      btnContainer.appendChild(endMsg);
    }
  }

  // Scroll to results only on initial search
  if (isNewSearch) {
    container.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    // Only smooth scroll if anchor starts with # and isn't just "#"
    const href = this.getAttribute('href');
    if (href !== '#' && href.startsWith('#')) {
      e.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth'
        });
      }
    }
  });
});
