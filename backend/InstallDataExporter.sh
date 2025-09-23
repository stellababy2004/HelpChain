#!/bin/sh

OS_ARCH=$(uname -m)

INSTALL_PATH="/opt"

BOOLEAN_TRUE="true"
BOOLEAN_FALSE="false"
MATCH_PHRASE_64BIT="64"
MATCH_PHRASE1_ARM="arm"
MATCH_PHRASE2_ARM="aarch"
QUIET="-q"
NOT_QUIET="-nq"
DOWNLOAD_ONLY="-downloadonly"

PRINT_OUTPUT=$NOT_QUIET
DO_DOWNLOAD_ONLY=$BOOLEAN_FALSE

DOWNLOAD_URL=""
PACKAGE_ZIP=""

LICENSE_KEY=""

IS_ARM=$BOOLEAN_FALSE
IS_NOTARM=$BOOLEAN_FALSE
IS_32BIT=$BOOLEAN_FALSE
IS_64BIT=$BOOLEAN_FALSE

PrintToTerminal() {
	if [ $PRINT_OUTPUT = $NOT_QUIET ]; then
		echo "$@"
	fi
}

############### site24x7 ###############

PACKAGE_NAME="S247DataExporter"
SUPPORT_MAILID="support@site24x7.com"
LICENSE_KEY="${S247_LICENSE_KEY}"

SetDownloadDomain() {

	case "$LICENSE_KEY" in
	eu_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.eu"
		;;
	cn_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.cn"
		;;
	in_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.in"
		;;
	au_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.net.au"
		;;
	jp_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.jp"
		;;
	ca_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.ca"
		;;
	uk_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.uk"
		;;
	sa_*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.sa"
		;;
	aa_*)
		DOWNLOAD_DOMAIN="http://staticdownloads.localsite24x7.com"
		;;
	ab_*)
		DOWNLOAD_DOMAIN="http://staticdownloads.localsite24x7.com"
		;;
	*)
		DOWNLOAD_DOMAIN="https://staticdownloads.site24x7.com"
		;;
	esac
}

SetDownloadPath() {

	#Have only true check
	if [ "$IS_NOTARM" = "$BOOLEAN_TRUE" ] && [ "$IS_32BIT" = "$BOOLEAN_TRUE" ]; then
		DOWNLOAD_PATH="apminsight/S247DataExporter/linux/386"
	elif [ "$IS_NOTARM" = "$BOOLEAN_TRUE" ] && [ "$IS_64BIT" = "$BOOLEAN_TRUE" ]; then
		DOWNLOAD_PATH="apminsight/S247DataExporter/linux/amd64"
	elif [ "$IS_ARM" = "$BOOLEAN_TRUE" ] && [ "$IS_32BIT" = "$BOOLEAN_TRUE" ]; then
		DOWNLOAD_PATH="apminsight/S247DataExporter/linux/arm"
	elif [ "$IS_ARM" = "$BOOLEAN_TRUE" ] && [ "$IS_64BIT" = "$BOOLEAN_TRUE" ]; then
		DOWNLOAD_PATH="apminsight/S247DataExporter/linux/arm64"
	else
		PrintToTerminal "Info: $OS_ARCH not supported in this version"
		ContactSupport
	fi

}

SetPackageZip() {
    PACKAGE_ZIP="${PACKAGE_NAME}.zip"
}

SetDownloadURL() {
    PrintToTerminal "Action: Setting Download url"

    SetDownloadDomain
    SetDownloadPath
    SetPackageZip

    DOWNLOAD_URL="${DOWNLOAD_DOMAIN}/${DOWNLOAD_PATH}/${PACKAGE_ZIP}"

    PrintToTerminal "Info: Download URL set as $DOWNLOAD_URL"
}

##########################################

ContactSupport() {
	PrintToTerminal "Info: Installation failed, Kindly contact support $SUPPORT_MAILID"
	exit 1
}

CheckFlags() {
	for arg in "$@"; do
		if [ "$arg" = $QUIET ]; then
			PRINT_OUTPUT=$QUIET
		fi
		if [ "$arg" = $DOWNLOAD_ONLY ]; then
			DO_DOWNLOAD_ONLY=$BOOLEAN_TRUE
		fi
	done
}

CheckBit() {
	PrintToTerminal "Action: Checking if Operating System is 32 or 64 bit"

	if echo "${OS_ARCH}" | grep -i -q "${MATCH_PHRASE_64BIT}"; then
		IS_64BIT=$BOOLEAN_TRUE
		PrintToTerminal "Info: Detected as 64bit"
	else
		IS_32BIT=$BOOLEAN_TRUE
		PrintToTerminal "Info: Detected as 32bit"
	fi
}

CheckARM() {
	PrintToTerminal "Action: Checking if ARM achitecture"

	if echo "${OS_ARCH}" | grep -i -q "${MATCH_PHRASE1_ARM}"; then
		IS_ARM=$BOOLEAN_TRUE
		PrintToTerminal "Info: Detected as ARM"
	elif echo "${OS_ARCH}" | grep -i -q "${MATCH_PHRASE2_ARM}"; then
		IS_ARM=$BOOLEAN_TRUE
		PrintToTerminal "Info: Detected as ARM"
	else
		IS_NOTARM=$BOOLEAN_TRUE
		PrintToTerminal "Info: Detected as not ARM"
	fi
}

DownloadPackage() {
	PrintToTerminal "Action: Downloading package"
	cd "$INSTALL_PATH" || {
		PrintToTerminal "Change Directory failed, check directory name"
		exit 1
	}
	wget -O "$PACKAGE_ZIP" "$DOWNLOAD_URL"
}

RemoveDownloads() {
	PrintToTerminal "Action: Removing downloaded files"

	#condition is added for safety, to avoid unwanted removal of necesssary files
	case "${PACKAGE_ZIP}" in
	${PACKAGE_NAME}*)
		ZIP_LOCATION="$INSTALL_PATH/$PACKAGE_ZIP"
		rm "$ZIP_LOCATION"
		;;
	*)
		PrintToTerminal "Error: Unable to remove downloaded files"
		;;
	esac
}

VerifyChecksum() {
	PrintToTerminal "Action: Verifying checksum"

	ZIP_LOCATION="$INSTALL_PATH/$PACKAGE_ZIP"
	ZIP_CHECKSUM=$(sha256sum "$ZIP_LOCATION" | awk '{print $1}')

	CHECKSUM_URL="${DOWNLOAD_URL}.sha256"
	LIVE_CHECKSUM="$(wget -qO- $CHECKSUM_URL | cut -f1 -d' ')"

	PrintToTerminal "Info: Checksum of downloaded agent: $ZIP_CHECKSUM"
	PrintToTerminal "Info: Checksum of live agent: $LIVE_CHECKSUM"

	if [ "$ZIP_CHECKSUM" != "$LIVE_CHECKSUM" ]; then
		PrintToTerminal "Status: Checksum validation failed. Please retry after some time"
		RemoveDownloads
		ContactSupport
	else
		PrintToTerminal "Status: Checksum verification successful"
	fi
}

UnzipPackage() {
	PrintToTerminal "Action: Unzipping package"

	cd "$INSTALL_PATH" || {
		PrintToTerminal "Info: Change Directory failed, check directory name"
		exit 1
	}
	unzip -o "$PACKAGE_ZIP" || {
		PrintToTerminal "Info: Unzip failed"
		exit 1
	}
}

InstallPackage() {
	if [ "$DO_DOWNLOAD_ONLY" = "$BOOLEAN_TRUE" ]; then
		PrintToTerminal "Action: Download only flag set, skipping installation"
		PrintToTerminal "Info: Kindly start the service manually"
	else
		PrintToTerminal "Action: Installing package"
		sh "${INSTALL_PATH}/${PACKAGE_NAME}/bin/service.sh" install "$@"
	fi
}

SetLicenseKey() {

	PrintToTerminal "Action: Checking for Licensekey"

	if [ -z "$LICENSE_KEY" ]; then

		for arg in "$@"; do
			PARAM=$arg
			VALUE="$2"

			case $PARAM in
			-lk | -license.key)
				LICENSE_KEY="$VALUE"
				;;
			esac
			shift
		done

		if [ -n "$LICENSE_KEY" ]; then
			PrintToTerminal "Info: License key updated from CLI"
		fi
	else
		PrintToTerminal "Info: License key updated from ENV"
	fi

	if [ -z "$LICENSE_KEY" ]; then
		PrintToTerminal "Info: License key not found in ENV / CLI"
		ContactSupport
	fi
}

main() {
	CheckFlags "$@"
	SetLicenseKey "$@"
	CheckBit
	CheckARM
	SetDownloadURL
	DownloadPackage
	VerifyChecksum
	UnzipPackage
	RemoveDownloads
	InstallPackage "$@"
}

main "$@"
