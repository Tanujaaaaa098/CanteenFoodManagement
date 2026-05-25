#include <iostream>
using namespace std;
int main() {
    int n, key;
    cout << "Enter number of elements: ";
    cin >> n;
    int arr[n];
    cout << "Enter " << n << " elements in sorted order:\n";
    for(int i = 0; i < n; i++) {
   cin >> arr[i]; }
    cout << "Enter element to search: ";
    cin >> key;
    int low = 0, high = n - 1;
    bool found = false;
    while(low <= high) {
        int mid = (low + high) / 2;
        if(arr[mid] == key) {
            cout << "Element " << key << " found at position " << mid + 1 << endl;
            found = true;
            break;}
        else if(arr[mid] < key)
            low = mid + 1;
        else       high = mid - 1;}
    if(!found)
        cout << "Element " << key << " not found in array." << endl;
    return 0;} 
