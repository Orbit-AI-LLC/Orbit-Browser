; Orbit Browser for Windows: installs for the person running it (no
; administrator needed), in %LOCALAPPDATA%\Programs\Orbit Browser.
;
; scripts/build.py compiles it with makensis, passing:
;   VERSION  Orbit Browser's version        ARCH     x64 or arm64
;   SOURCE   the finished app folder         OUTFILE  the installer to write
;   ICON     branding/windows/firefox.ico   FILEVERSION  the version as four numbers
;
; Besides the files and shortcuts it registers Orbit Browser with Windows as
; a browser under its own name (Settings > Apps > Default apps lists it), and
; offers to open that page at the end. A new version installs over the old
; one; people's profiles live elsewhere and are left alone, by the
; uninstaller too.
;
; Orbit Browser updates itself with it (browser/modules/OrbitUpdates.sys.mjs):
; as it quits it runs the new version's installer with /S /UPDATE, and
; /RELAUNCH for Restart Now. /UPDATE waits for the browser to close instead
; of asking, and leaves a desktop shortcut the person deleted deleted;
; /RELAUNCH opens the browser again once it's done.

Unicode true
ManifestDPIAware true
SetCompressor /SOLID lzma
RequestExecutionLevel user

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

!define APP "Orbit Browser"
!define EXE "firefox.exe"
!define REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrbitBrowser"
!define CLIENTKEY "Software\Clients\StartMenuInternet\${APP}"
!define HTMLCLASS "OrbitBrowserHTML"
!define URLCLASS "OrbitBrowserURL"

Var Updating
Var Relaunch

Name "${APP}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "${REGKEY}" "InstallLocation"
BrandingText "${APP} ${VERSION}"
VIProductVersion "${FILEVERSION}"
VIAddVersionKey "FileVersion" "${FILEVERSION}"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "CompanyName" "Orbit LLC"
VIAddVersionKey "FileDescription" "${APP} installer"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "Orbit Browser is built on Firefox: © Firefox and Mozilla Developers, MPL 2.0"

!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Open ${APP}"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Choose ${APP} as my default browser"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION OpenDefaultApps
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  !if "${ARCH}" == "x64"
    ${IfNot} ${RunningX64}
      MessageBox MB_ICONSTOP "${APP} needs 64-bit Windows."
      Abort
    ${EndIf}
  !endif
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/UPDATE" $1
  ${IfNot} ${Errors}
    StrCpy $Updating 1
  ${EndIf}
  ClearErrors
  ${GetOptions} $0 "/RELAUNCH" $1
  ${IfNot} ${Errors}
    StrCpy $Relaunch 1
  ${EndIf}
FunctionEnd

Function .onInstSuccess
  ${If} $Relaunch == 1
    Exec '"$INSTDIR\${EXE}"'
  ${EndIf}
FunctionEnd

; The old version's files go first (a file Firefox dropped in a new version
; would otherwise linger), which only works once Orbit Browser is closed. An
; update the browser started as it quit waits up to a minute for it to close.
Function RemoveOldFiles
  ${If} ${FileExists} "$INSTDIR\${EXE}"
    StrCpy $2 0
    retry:
    ClearErrors
    Delete "$INSTDIR\${EXE}"
    ${If} ${Errors}
      ${If} $Updating == 1
        ${If} $2 < 120
          IntOp $2 $2 + 1
          Sleep 500
          Goto retry
        ${EndIf}
        Abort
      ${EndIf}
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Close ${APP}, then choose Retry." IDRETRY retry
      Abort
    ${EndIf}
    RMDir /r "$INSTDIR"
  ${EndIf}
FunctionEnd

Function OpenDefaultApps
  ExecShell "open" "ms-settings:defaultapps?registeredAppUser=${APP}"
FunctionEnd

Section "Install"
  Call RemoveOldFiles
  SetOutPath "$INSTDIR"
  File /r "${SOURCE}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall ${APP}.exe"

  CreateShortcut "$SMPROGRAMS\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP} Private Window.lnk" "$INSTDIR\private_browsing.exe" "" "$INSTDIR\private_browsing.exe" 0
  ${If} $Updating != 1
  ${OrIf} ${FileExists} "$DESKTOP\${APP}.lnk"
    CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0
  ${EndIf}

  ; Apps & features
  WriteRegStr HKCU "${REGKEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${REGKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${REGKEY}" "Publisher" "Orbit LLC"
  WriteRegStr HKCU "${REGKEY}" "URLInfoAbout" "https://orbit.com.ai/"
  WriteRegStr HKCU "${REGKEY}" "DisplayIcon" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "${REGKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${REGKEY}" "UninstallString" '"$INSTDIR\Uninstall ${APP}.exe"'
  WriteRegStr HKCU "${REGKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall ${APP}.exe" /S'
  WriteRegDWORD HKCU "${REGKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${REGKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${REGKEY}" "EstimatedSize" $0

  ; A browser Windows knows by name: what it opens and the classes that open it.
  ; Firefox's own command line for links from other apps: -osint -url "%1".
  WriteRegStr HKCU "Software\Classes\${HTMLCLASS}" "" "${APP} HTML Document"
  WriteRegStr HKCU "Software\Classes\${HTMLCLASS}\Application" "ApplicationName" "${APP}"
  WriteRegStr HKCU "Software\Classes\${HTMLCLASS}\Application" "ApplicationIcon" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "Software\Classes\${HTMLCLASS}\DefaultIcon" "" "$INSTDIR\${EXE},1"
  WriteRegStr HKCU "Software\Classes\${HTMLCLASS}\shell\open\command" "" '"$INSTDIR\${EXE}" -osint -url "%1"'
  WriteRegStr HKCU "Software\Classes\${URLCLASS}" "" "${APP} URL"
  WriteRegStr HKCU "Software\Classes\${URLCLASS}" "URL Protocol" ""
  WriteRegStr HKCU "Software\Classes\${URLCLASS}\Application" "ApplicationName" "${APP}"
  WriteRegStr HKCU "Software\Classes\${URLCLASS}\Application" "ApplicationIcon" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "Software\Classes\${URLCLASS}\DefaultIcon" "" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "Software\Classes\${URLCLASS}\shell\open\command" "" '"$INSTDIR\${EXE}" -osint -url "%1"'

  WriteRegStr HKCU "${CLIENTKEY}" "" "${APP}"
  WriteRegStr HKCU "${CLIENTKEY}\DefaultIcon" "" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "${CLIENTKEY}\shell\open\command" "" '"$INSTDIR\${EXE}"'
  WriteRegStr HKCU "${CLIENTKEY}\Capabilities" "ApplicationName" "${APP}"
  WriteRegStr HKCU "${CLIENTKEY}\Capabilities" "ApplicationIcon" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "${CLIENTKEY}\Capabilities" "ApplicationDescription" "The Orbit browser: Firefox's engine, Orbit AI in the sidebar and Orbit Pass built in."
  WriteRegStr HKCU "${CLIENTKEY}\Capabilities\StartMenu" "StartMenuInternet" "${APP}"
  !macro Associate EXT
    WriteRegStr HKCU "${CLIENTKEY}\Capabilities\FileAssociations" "${EXT}" "${HTMLCLASS}"
    WriteRegStr HKCU "Software\Classes\${EXT}\OpenWithProgids" "${HTMLCLASS}" ""
  !macroend
  !insertmacro Associate ".htm"
  !insertmacro Associate ".html"
  !insertmacro Associate ".shtml"
  !insertmacro Associate ".xht"
  !insertmacro Associate ".xhtml"
  !insertmacro Associate ".svg"
  !insertmacro Associate ".webp"
  !insertmacro Associate ".pdf"
  WriteRegStr HKCU "${CLIENTKEY}\Capabilities\URLAssociations" "http" "${URLCLASS}"
  WriteRegStr HKCU "${CLIENTKEY}\Capabilities\URLAssociations" "https" "${URLCLASS}"
  WriteRegStr HKCU "Software\RegisteredApplications" "${APP}" "${CLIENTKEY}\Capabilities"

  ; Tell Explorer the associations changed (SHCNE_ASSOCCHANGED).
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP} Private Window.lnk"
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${REGKEY}"
  DeleteRegKey HKCU "${CLIENTKEY}"
  DeleteRegKey HKCU "Software\Classes\${HTMLCLASS}"
  DeleteRegKey HKCU "Software\Classes\${URLCLASS}"
  DeleteRegValue HKCU "Software\RegisteredApplications" "${APP}"
  !macro Unassociate EXT
    DeleteRegValue HKCU "Software\Classes\${EXT}\OpenWithProgids" "${HTMLCLASS}"
  !macroend
  !insertmacro Unassociate ".htm"
  !insertmacro Unassociate ".html"
  !insertmacro Unassociate ".shtml"
  !insertmacro Unassociate ".xht"
  !insertmacro Unassociate ".xhtml"
  !insertmacro Unassociate ".svg"
  !insertmacro Unassociate ".webp"
  !insertmacro Unassociate ".pdf"
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
SectionEnd
