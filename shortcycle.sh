#!/bin/bash
# shortcycle|longcycle - make (and sometimes destroy) thin clones

src_path='/var/lib/libvirt/images'
img_path="${src_path}"
no_internet=0
start_time=$(date +%s)

while getopts "nes:" flag; do
  case "${flag}" in
    n) no_internet=1 ;;
    e) img_path='/var/lib/libvirt/images.ephemeral';;
    s) hubshare_cfg="${OPTARG} ${hubshare_cfg}";;
  esac
done

template=${@:$OPTIND:1}


function cleanup {
  if [[ -n "${file_list}" ]]; then
    for img_file in ${file_list}; do
      if [[ -f "{${img_file}" ]]; then
        rm -f ${img_file}
      fi
    done
  fi

  if virsh vcpucount "${clone}" &> /dev/null; then
    virsh destroy "${clone}"
    virsh undefine "${clone}"
  fi
}

function format_elapsed {
  printf '%s' "${1}"
  start=${2}
  end=${3}
  elapsed=$((end-start))

  if [[ ${elapsed} -gt 86400 ]]; then
    days=$((elapsed/86400))
    elapsed=$((elapsed-(days*86400)))
    printf '%s days, ' ${days}
  fi

  if [[ ${elapsed} -gt 3600 ]]; then
    hours=$((elapsed/3600))
    elapsed=$((elapsed-(hours*3600)))
    printf '%s hours, ' ${hours}
  fi

  if [[ ${elapsed} -gt 60 ]]; then
    minutes=$((elapsed/60))
    elapsed=$((elapsed-(minutes*60)))
    printf '%s minutes, ' ${minutes}
  fi

  echo "${elapsed} seconds"
}

function add_hubshare {
  echo "Waiting for hubshare to find ${clone}"
  if ! hubshare wait "${clone}" > /dev/null; then
    echo "No hubshares added"
  else
    for share in ${hubshare_cfg}; do
      share_name=$(cut -d'=' -f1 <<< "${share}")
      share_path=$(cut -d'=' -f2 <<< "${share}")

      if grep -q 'shortcycle' <<< "${0}"; then
        echo "Adding temp hubshare ${share_name} (${share_path})"
        hubshare add "${clone}" "${share_path}" "${share_name}"
      else
        echo "Adding permanent hubshare ${share_name} (${share_path})"
        hubshare -p add "${clone}" "${share_path}" "${share_name}"
      fi
    done
  fi
}

# Verify that we're working on a template; other VMs aren't meant for this
if ! grep -s '\-template' <<< "${template}"; then
  echo "${template} is not a template VM"
  exit 1
fi

# Make sure that the template isn't running
template_state=$(virsh dominfo "${template}" | grep -Po 'State:.*')
if [[ -z "${template_state}" ]]; then
  echo "No VM named '${template}'"
  exit 1
fi

if [[ "$(awk '{print $NF}' <<< "${template_state}")" == "running" ]]; then
  echo "Template VM is still running"
  exit 1
fi

# Come up with a name for our clone
if grep -q 'shortcycle' <<< "${0}"; then
  base_name='-tempclone'
else
  base_name=''
fi

clone=$(sed "s/-template/${base_name}-0/g" <<< ${template})
if [[ "${clone}" == "${template}" ]]; then
  echo "Rename error; exiting"
  exit 1
fi

ordinal=0
while virsh dominfo "${clone}" &> /dev/null; do
  echo "Clone ${clone} already exists"
  ordinal=$((ordinal+1))
  clone=$(sed "s/-template/${base_name}-${ordinal}/g" <<< ${template})
done

# Output the clone VM name in a way that's easy to grep
# grep -Po '(?<=##### clone VM name: ).*?(?=#####)'
echo "##### clone VM name: ${clone} #####"

# Make thin clones of the storage
template_drives=$(virsh domblklist "${template}" | grep "${src_path}")
skip_copy=""
file_list=""
if [[ -n "${template_drives}" ]]; then
  while read -e template_drive; do
    backing=$(awk '{print $NF}' <<< "${template_drive}")
    drive=$(awk '{print $1}' <<< "${template_drive}")
    new_file="${img_path}/${clone}-${drive}.qcow2"
    if ! qemu-img create -b "${backing}" -F qcow2 -f qcow2 "${new_file}"; then
      echo "Failed to thin-clone of ${backing}"
      exit 1
    fi
    skip_copy="${skip_copy} --skip-copy=${drive}"
    file_list="${file_list} --file ${backing}"
  done <<< "${template_drives}"
else
  skip_copy='--auto-clone'
fi

# Clone the VM, skipping the hard drives
if ! virt-clone ${skip_copy} ${file_list} --original "${template}" --name "${clone}"; then
  echo "Failed to clone the VM"
  cleanup
  exit 1
fi

if [[ -n "${template_drives}" ]]; then
  # Change the drive references in the clone VM to the thin cloned storage
  while read -e template_drive; do
    drive=$(awk '{print $1}' <<< "${template_drive}")
    qcow="${img_path}/${clone}-${drive}.qcow2"
    if ! virt-xml "${clone}" --edit target=${drive} --disk "driver_type=qcow2,path=${qcow}"; then
      echo "Failed to switch clone VM to clone storage ${drive}"
      cleanup
    fi
  done <<< "${template_drives}"
fi

# If the no_internet flag is set, remove the default network
if [[ "${no_internet}" == "1" ]]; then
  vdl=$(virsh domiflist "${clone}" | grep -P 'network\s+default')
  mac=$(awk '{print $NF}' <<< "${vdl}")
  if ! virsh detach-interface "${clone}" network --mac "${mac}" --persistent; then
    echo "WARNING: failed to remove default network interface; ${clone} will have Internet access!"
  fi
fi

# If there are hubshares defined on in arguments, make sure that the VM has an
# interface on br-hub
if [[ -n "${hubshare_cfg}" ]]; then
  if ! virsh domiflist ${clone} | awk '{print $3}' | grep -q 'br-hub'; then
    new_mac=$(hexdump -n 6 -ve '1/1 "%.2x "' /dev/random | awk -v a="2,6,a,e" -v r="$RANDOM" 'BEGIN{srand(r);}NR==1{split(a,b,",");r=int(rand()*4+1);printf "%s%s:%s:%s:%s:%s:%s\n",substr($1,0,1),b[r],$2,$3,$4,$5,$6}')
    virsh attach-interface --domain ${clone} --type network \
        --source br-hub --model virtio \
        --mac ${new_mac} --config
  fi
fi

# Start the clone VM
if ! virsh start "${clone}"; then
  echo "Failed to start ${clone}; it needs to be started manually"
  exit 1
else
  sleep 2
fi

vm_start_time=$(date +%s)
format_elapsed "Cloned & started VM in " ${start_time} ${vm_start_time}

# Show the console window
virt-manager --connect "${LIBVIRT_DEFAULT_URI}" --show-domain-console "${clone}"

if [[ -n "${hubshare_cfg}" ]]; then
  if grep -q 'shortcycle' <<< "${0}"; then
    add_hubshare &
  else
    add_hubshare
  fi
fi

if grep -q 'shortcycle' <<< "${0}"; then
  # Wait for the user to shutdown the clone VM
  echo "Use ${clone}; when it shuts down, this script will clean it up"
  until virsh dominfo "${clone}" | grep -Pos 'State:\s*shut off'; do
    sleep 3
  done

  vm_stop_time=$(date +%s)
  format_elapsed "Clone VM ran for " ${vm_start_time} ${vm_stop_time}

  echo "${clone} stopped; cleaning up"

  if [[ -n "$(ls ${img_path}/${clone}-*.qcow2 2> /dev/null)" ]]; then
    if ! shred -vz ${img_path}/${clone}-*.qcow2; then
      echo "Failed to shred storage"
      exit 1
    fi
  fi

  if nvram=$(virsh dumpxml "${clone}" | grep -Po '(?<=<nvram>).*?(?=</nvram>)'); then
    # If the clone has nvram, it has to be handled differently
    sudo shred -v "${nvram}"
    virsh undefine "${clone}" --nvram
  else
    virsh undefine "${clone}"
  fi

  if [[ "${?}" != "0" ]]; then
    echo "Failed to undefine VM"
  else
    rm -f ${img_path}/${clone}-*.qcow2
  fi

  if [[ -f "/var/log/libvirt/qemu/${clone}.log" ]]; then
    sudo shred -uv "/var/log/libvirt/qemu/${clone}.log"
  fi

  if [[ -n "${hubshare_cfg}" ]]; then
    echo "Removing hubshares"
    hubshare delete "${clone}"
  fi
fi

if grep -q 'shortcycle' <<< "${0}"; then
  format_elapsed "Clone VM cleanup completed in " ${vm_stop_time} $(date +%s)
fi
format_elapsed "Total ${0} time was " ${start_time} $(date +%s)
