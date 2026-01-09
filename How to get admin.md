# How to Get Into an Admin Account

1. **On the login screen**, press **Restart** on the bottom right of the screen **while holding Shift**.

2. When **Startup Repair** appears, go to:

   * `Troubleshoot > Advanced Options > Command Prompt`

3. In **Command Prompt**, type:

   ```
   notepad
   ```

   and press **Enter**.

4. In **Notepad**, go to `File > Open`.

5. Navigate to the target drive (likely `D:\`), or the drive that contains familiar users in `\Windows\Users`.

6. Go to the directory:

   ```
   \Windows\System32
   ```

7. At the bottom of the file explorer window, change:

   ```
   Text Documents (*.txt)
   ```

   to:

   ```
   All Files (*.*)
   ```

8. Scroll down and find `cmd.exe`. Right-click it and select **Open**.

9. In the new command prompt window, type:

   ```
   rename sethc.exe sethc-old.exe && copy cmd.exe sethc.exe
   ```

   > You will only have to do this rename **once per computer**. You will need to do it again if the computer is reinstalled.

10. Close **Notepad** and both **Command Prompts**, and return to **Advanced Options**.

11. Press **Startup Settings** and click the **Restart** button when it appears.

12. When the next blue menu appears, press:

* `F8` or, on a laptop keyboard, `Fn + F8`
   * This will enable the following setting: `8) Disable early launch anti-malware protection`.

13. Once at the login screen, **press Shift 5 times quickly** (either left or right Shift, not both). A **Command Prompt** window should appear.

14. In the command prompt, type:

```
net user Administrator *
```

15. Enter a password you'll remember and re-enter it to verify the change.

> You can now login to the computer with `Administrator` as the username and the password you chose.

## Future Admin Access

Since your password isn't saved acorss restarts, to log in as admin in the future:

* Press **Shift + Restart**
* Navigate to: `Troubleshoot > Advanced Options > Startup Settings > Restart`
* Press `F8` at the next menu
* Open command prompt by clicking **Shift** quickly 5 times
* Run `net user Administrator *` and enter any password twice

* Proceed with admin login at the lock screen

