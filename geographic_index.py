"""
Geographic clustering and state-based organization for hospital networks.
Reduces sorting dataset by grouping hospitals into regional zones.
"""

from typing import Dict, List, Set


# Define Indian states and their neighboring states
INDIA_STATES = {
    "Delhi": ["Punjab", "Haryana", "Uttar Pradesh"],
    "Punjab": ["Delhi", "Haryana", "Himachal Pradesh", "Jammu & Kashmir"],
    "Haryana": ["Delhi", "Punjab", "Uttar Pradesh", "Rajasthan"],
    "Uttar Pradesh": ["Delhi", "Haryana", "Bihar", "Madhya Pradesh", "Rajasthan"],
    "Rajasthan": ["Haryana", "Uttar Pradesh", "Gujarat", "Madhya Pradesh"],
    "Gujarat": ["Rajasthan", "Madhya Pradesh"],
    "Madhya Pradesh": ["Rajasthan", "Uttar Pradesh", "Gujarat", "Maharashtra", "Chhattisgarh"],
    "Maharashtra": ["Madhya Pradesh", "Chhattisgarh", "Telangana", "Karnataka"],
    "Karnataka": ["Maharashtra", "Telangana", "Andhra Pradesh", "Tamil Nadu"],
    "Tamil Nadu": ["Karnataka", "Andhra Pradesh", "Telangana"],
    "Andhra Pradesh": ["Maharashtra", "Karnataka", "Tamil Nadu", "Telangana"],
    "Telangana": ["Maharashtra", "Chhattisgarh", "Andhra Pradesh", "Karnataka"],
    "Chhattisgarh": ["Madhya Pradesh", "Maharashtra", "Telangana", "Jharkhand", "Odisha"],
    "Jharkhand": ["Chhattisgarh", "Odisha", "Bihar", "West Bengal"],
    "Odisha": ["Chhattisgarh", "Jharkhand", "West Bengal"],
    "West Bengal": ["Jharkhand", "Odisha", "Bihar"],
    "Bihar": ["Uttar Pradesh", "West Bengal", "Jharkhand"],
    "Himachal Pradesh": ["Punjab", "Jammu & Kashmir"],
    "Jammu & Kashmir": ["Punjab", "Himachal Pradesh"],
}


class GeographicIndex:
    """
    Organizes hospitals by geographic regions (states).
    Dramatically reduces sorting dataset.
    """
    
    def __init__(self):
        # state -> [hospital_ids]
        self.hospitals_by_state: Dict[str, List[int]] = {state: [] for state in INDIA_STATES.keys()}
        # state -> set of nearby state names
        self.nearby_states_cache: Dict[str, Set[str]] = {}
    
    def add_hospital_to_index(self, hospital_id: int, state: str) -> None:
        """Add hospital to geographic index."""
        if state not in self.hospitals_by_state:
            self.hospitals_by_state[state] = []
        self.hospitals_by_state[state].append(hospital_id)
    
    def get_nearby_states(self, state: str) -> Set[str]:
        """
        Get nearby states cache to avoid recalculation.
        
        Returns:
            Set of nearby state names + the state itself
        """
        if state in self.nearby_states_cache:
            return self.nearby_states_cache[state]
        
        # Include the state itself + neighbors
        nearby = {state}
        if state in INDIA_STATES:
            nearby.update(INDIA_STATES[state])
        
        self.nearby_states_cache[state] = nearby
        return nearby
    
    def get_hospitals_in_regions(self, state: str, include_nearby: bool = True) -> List[int]:
        """
        Get hospital IDs from a state and optionally nearby states.
        
        Args:
            state: Source state
            include_nearby: If True, include nearby states as well
        
        Returns:
            List of hospital IDs in the region(s)
        """
        hospital_ids = []
        
        if include_nearby:
            # Get state + nearby states
            region_states = self.get_nearby_states(state)
        else:
            # Only the state itself
            region_states = {state}
        
        # Collect all hospitals from these states
        for s in region_states:
            if s in self.hospitals_by_state:
                hospital_ids.extend(self.hospitals_by_state[s])
        
        return hospital_ids
    
    def get_region_stats(self) -> Dict:
        """Get statistics about geographic distribution."""
        stats = {}
        for state, hospital_ids in self.hospitals_by_state.items():
            if hospital_ids:
                nearby = self.get_nearby_states(state)
                total_in_region = sum(
                    len(self.hospitals_by_state.get(s, []))
                    for s in nearby
                )
                stats[state] = {
                    "hospitals_in_state": len(hospital_ids),
                    "nearby_states": len(nearby) - 1,  # Exclude self
                    "total_in_region": total_in_region
                }
        return stats


def calculate_search_reduction(state: str) -> Dict:
    """
    Calculate how much data reduction regional search provides.
    
    Example: Instead of sorting 1000 hospitals, sort only 150 in your region
    """
    geo_index = GeographicIndex()
    nearby_states = geo_index.get_nearby_states(state)
    num_nearby = len(nearby_states)
    
    return {
        "state": state,
        "nearby_states_count": num_nearby - 1,  # Exclude self
        "region_coverage": f"1 state + {num_nearby - 1} neighboring states",
        "reduction_factor": "~3-5x" if num_nearby >= 4 else "~2x",
        "sorting_improvement": "Much faster - reduced dataset"
    }

