set -lx is_terragrunt_installed (type -q terragrunt; echo $status)

function add_terraform_abbr --argument-names alias_name command_name
    abbr --add -g "tf$alias_name" terraform $command_name
    if test $is_terragrunt_installed -eq 0
        # If terragrunt is installed, add terragrunt aliases
        abbr --add -g "tg$alias_name" terragrunt $command_name
        abbr --add -g "tgra$alias_name" terragrunt run --all $command_name
    else
        # If terragrunt is not installed, alias terragrunt to terraform
        # It's a minor thing, but helps with muscle memory of typing tg all the time
        abbr --add -g "tg$alias_name" terraform $command_name
        abbr --add -g "tgra$alias_name" terraform $command_name
    end
end

abbr --add -g tf terraform
abbr --add -g tg terragrunt
add_terraform_abbr p plan
add_terraform_abbr i init
add_terraform_abbr iu 'init -upgrade'
add_terraform_abbr a apply
add_terraform_abbr aa "apply -auto-approve"
add_terraform_abbr v validate
add_terraform_abbr f fmt

if test $is_terragrunt_installed -eq 0
    abbr --add -g tg terragrunt
else
    abbr --add -g tg terraform
    # If terragrunt is not installed, alias terragrunt to terraform
    alias terragrunt="terraform"
    abbr terragrunt terraform
end

# Delete the function after use
functions -e add_terraform_abbr
set --erase is_terragrunt_installed
